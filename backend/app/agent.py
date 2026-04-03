"""Microsoft Agent Framework agent for TfL Explorer.

Creates and configures the transport assistant agent with:
- Neo4j memory integration (context provider, message store)
- Transport tools (spatial queries, route finding, live status)
- Memory tools (preferences, knowledge, reasoning traces)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from agent_framework import Agent, Message, tool
from agent_framework.openai import OpenAIChatClient

from neo4j_agent_memory.integrations.microsoft_agent import (
    Neo4jMicrosoftMemory,
    create_memory_tools,
    record_agent_trace,
)

from .config import settings
from .tfl_client import TfLClient
from .tools.transport import get_transport_tools

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are TfL Explorer, a knowledgeable London transport assistant with memory capabilities.

You help users navigate the Transport for London network by:
1. Finding stations near locations (using spatial queries on the graph)
2. Planning routes between stations (using graph traversal)
3. Checking line status and disruptions (using live TfL data)
4. Finding cycle hire bike points with availability
5. Answering questions about the transport network

Key behaviors:
- When users mention places, use find_nearest_stations with coordinates.
  Common London landmarks: Big Ben (51.5007, -0.1246), British Museum (51.5194, -0.1270),
  Tower Bridge (51.5055, -0.0754), Buckingham Palace (51.5014, -0.1419),
  Trafalgar Square (51.5080, -0.1281), London Eye (51.5033, -0.1195).
- When users ask about specific stations, use search_station or get_station_details.
- When users want directions, use find_route to find the shortest path.
- When users ask about a line, use get_line_stations to show all stations.
- Remember user preferences (preferred lines, home station, accessibility needs) using memory tools.
- Use remember_fact to store important knowledge as subject-predicate-object triples (e.g., "user" "lives near" "Waterloo").
- Use find_connection_path to discover how entities the user has discussed are connected in the knowledge graph.
- Use find_similar_items to find entities similar to ones the user mentions.
- Use find_important_entities to identify the most frequently discussed or central topics.
- Reference past conversations naturally when relevant.

Response format:
- Include station names and line names in your responses.
- When listing stations, mention their zone if relevant.
- When showing routes, describe the line changes needed.
- Be concise but informative. London transport users appreciate efficiency."""


def get_chat_client() -> OpenAIChatClient:
    """Create the OpenAI chat client."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")

    return OpenAIChatClient(
        api_key=settings.openai_api_key,
        model_id="gpt-4o",
    )


async def create_agent(
    memory: Neo4jMicrosoftMemory,
    tfl_client: TfLClient | None = None,
) -> Agent:
    """Create a transport assistant agent with Neo4j memory."""
    chat_client = get_chat_client()

    # Memory tools (search, preferences, knowledge, facts, traces, GDS graph algorithms)
    memory_tools = create_memory_tools(memory, include_gds_tools=True)

    # Transport tools (spatial queries, routes, live status)
    transport_tools = get_transport_tools(memory, tfl_client=tfl_client)

    all_tools = memory_tools + transport_tools

    agent = chat_client.as_agent(
        name="TfLExplorer",
        instructions=SYSTEM_PROMPT,
        tools=all_tools,
        context_providers=[memory.context_provider],
    )

    return agent


async def run_agent_stream(
    agent: Agent,
    message: str,
    memory: Neo4jMicrosoftMemory,
) -> AsyncGenerator[dict, None]:
    """Run the agent and stream responses.

    Yields SSE events: token, tool_call, tool_result, done, error.

    Message persistence is handled by the context provider's lifecycle hooks:
    - before_run(): loads conversation history and injects it as context
    - after_run(): saves input + response messages and triggers entity extraction

    We only need to record reasoning traces here (not managed by the provider).
    """
    tool_calls_for_trace = []

    try:
        # Pass only the current message — the context provider's before_run()
        # injects prior conversation history automatically
        full_response = ""
        async for update in agent.run([Message("user", [message])], stream=True):
            if update.text:
                full_response += update.text
                yield {
                    "event": "token",
                    "data": json.dumps({"content": update.text}),
                }

            for content in update.contents:
                if content.type == "function_call":
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({
                            "name": content.name,
                            "arguments": content.arguments,
                        }),
                    }
                elif content.type == "function_result":
                    tool_calls_for_trace.append({
                        "name": content.call_id,
                        "result": content.result,
                    })
                    yield {
                        "event": "tool_result",
                        "data": json.dumps({
                            "name": content.call_id,
                            "result": content.result,
                        }),
                    }

        # Record reasoning trace asynchronously (not managed by context provider)
        if full_response:
            async def _record_trace() -> None:
                try:
                    await record_agent_trace(
                        memory=memory,
                        messages=[
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": full_response[:500]},
                        ],
                        task=message,
                        tool_calls=tool_calls_for_trace,
                        outcome="success",
                        success=True,
                        generate_embedding=True,
                    )
                except Exception:
                    logger.exception("Error recording reasoning trace")

            asyncio.create_task(_record_trace())

    except Exception as e:
        logger.exception("Error in agent stream")
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)}),
        }
