"""Memory client setup and lifecycle management."""

from __future__ import annotations

import logging

from pydantic import SecretStr

from neo4j_agent_memory import MemoryClient, MemorySettings
from neo4j_agent_memory.config.settings import (
    EnrichmentConfig,
    ExtractionConfig,
    ExtractorType,
    GeocodingConfig,
    ResolutionConfig,
    SchemaConfig,
)
from neo4j_agent_memory.integrations.microsoft_agent import (
    Neo4jMicrosoftMemory,
)
from neo4j_agent_memory.integrations.microsoft_agent.gds import (
    GDSAlgorithm,
    GDSConfig,
)

from .config import settings

logger = logging.getLogger(__name__)

# Global memory client (managed via FastAPI lifespan)
memory_client: MemoryClient | None = None


def get_memory_settings() -> MemorySettings:
    """Create MemorySettings from environment."""
    return MemorySettings(
        neo4j={
            "uri": settings.neo4j_uri,
            "user": settings.neo4j_user,
            "password": SecretStr(settings.neo4j_password),
        },
        embedding={
            "provider": "openai",
            "model": "text-embedding-3-small",
            "api_key": (
                SecretStr(settings.openai_api_key) if settings.openai_api_key else None
            ),
        },
        extraction=ExtractionConfig(
            extractor_type=ExtractorType.LLM,
        ),
        # POLE+O entity schema: Location for stations, Organization for TfL,
        # Event for disruptions, Person for users
        schema_config=SchemaConfig(
            enable_subtypes=True,
        ),
        # Entity deduplication: handles "King's Cross" vs "Kings Cross St Pancras"
        resolution=ResolutionConfig(
            strategy="composite",
            fuzzy_threshold=0.85,
            semantic_threshold=0.8,
        ),
        # Geocoding for location entities (free Nominatim provider)
        geocoding=GeocodingConfig(
            enabled=True,
            provider="nominatim",
            user_agent="tfl-explorer",
        ),
        # Wikipedia enrichment for entities like "King's Cross"
        enrichment=EnrichmentConfig(
            enabled=True,
            background_enabled=True,
        ),
    )


async def init_memory_client() -> None:
    """Initialize the global memory client."""
    global memory_client
    logger.info("Connecting memory client to Neo4j...")
    memory_client = MemoryClient(get_memory_settings())
    await memory_client.connect()
    logger.info("Memory client connected.")


async def close_memory_client() -> None:
    """Close the global memory client."""
    global memory_client
    if memory_client:
        await memory_client.close()
        memory_client = None
        logger.info("Memory client disconnected.")


def get_memory_client() -> MemoryClient:
    """Get the global memory client."""
    if memory_client is None:
        raise RuntimeError("Memory client not initialized")
    return memory_client


async def create_memory(
    session_id: str, user_id: str | None = None
) -> Neo4jMicrosoftMemory:
    """Create a memory instance for a session."""
    client = get_memory_client()
    return Neo4jMicrosoftMemory(
        memory_client=client,
        session_id=session_id,
        user_id=user_id,
        include_short_term=True,
        include_long_term=True,
        include_reasoning=True,
        max_context_items=15,
        max_recent_messages=10,
        extract_entities=True,
        extract_entities_async=True,
        gds_config=GDSConfig(
            enabled=True,
            fallback_to_basic=True,
            use_pagerank_for_ranking=True,
            expose_as_tools=[
                GDSAlgorithm.SHORTEST_PATH,
                GDSAlgorithm.NODE_SIMILARITY,
                GDSAlgorithm.PAGERANK,
            ],
        ),
    )
