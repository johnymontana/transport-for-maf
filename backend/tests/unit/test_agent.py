"""Unit tests for agent creation and streaming."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestGetChatClient:
    """Test OpenAI chat client creation."""

    def test_raises_without_api_key(self):
        """Should raise ValueError when OPENAI_API_KEY is missing."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = None

        with patch("app.agent.settings", mock_settings):
            from app.agent import get_chat_client

            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                get_chat_client()

    def test_creates_client_with_api_key(self):
        """Should create OpenAIChatClient when key is set."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "sk-test"
        mock_client = MagicMock()

        with patch("app.agent.settings", mock_settings):
            with patch("app.agent.OpenAIChatClient", return_value=mock_client) as mock_cls:
                from app.agent import get_chat_client

                result = get_chat_client()
                mock_cls.assert_called_once_with(
                    api_key="sk-test",
                    model_id="gpt-4o",
                )
                assert result is mock_client


@pytest.mark.unit
class TestCreateAgent:
    """Test agent creation with tools and context providers."""

    @pytest.mark.asyncio
    async def test_agent_has_transport_and_memory_tools(self):
        """create_agent should combine memory + transport tools."""
        mock_memory = MagicMock()
        mock_memory.context_provider = MagicMock()

        mock_memory_tools = [MagicMock(name="search_memory"), MagicMock(name="remember_pref")]
        mock_transport_tools = [MagicMock(name="find_stations"), MagicMock(name="find_route")]

        mock_agent = MagicMock()
        mock_chat_client = MagicMock()
        mock_chat_client.as_agent = MagicMock(return_value=mock_agent)

        with patch("app.agent.get_chat_client", return_value=mock_chat_client):
            with patch("app.agent.create_memory_tools", return_value=mock_memory_tools):
                with patch("app.agent.get_transport_tools", return_value=mock_transport_tools):
                    from app.agent import create_agent

                    agent = await create_agent(mock_memory)

                    assert agent is mock_agent
                    call_kwargs = mock_chat_client.as_agent.call_args[1]
                    assert len(call_kwargs["tools"]) == 4  # 2 memory + 2 transport
                    assert call_kwargs["context_providers"] == [mock_memory.context_provider]
                    assert call_kwargs["name"] == "TfLExplorer"

    @pytest.mark.asyncio
    async def test_agent_with_tfl_client(self):
        """create_agent should pass tfl_client to transport tools."""
        mock_memory = MagicMock()
        mock_memory.context_provider = MagicMock()
        mock_tfl_client = MagicMock()

        mock_agent = MagicMock()
        mock_chat_client = MagicMock()
        mock_chat_client.as_agent = MagicMock(return_value=mock_agent)

        with patch("app.agent.get_chat_client", return_value=mock_chat_client):
            with patch("app.agent.create_memory_tools", return_value=[]):
                with patch("app.agent.get_transport_tools", return_value=[]) as mock_get_tools:
                    from app.agent import create_agent

                    await create_agent(mock_memory, tfl_client=mock_tfl_client)
                    mock_get_tools.assert_called_once_with(mock_memory, tfl_client=mock_tfl_client)


@pytest.mark.unit
class TestSystemPrompt:
    """Test system prompt content."""

    def test_prompt_mentions_key_capabilities(self):
        from app.agent import SYSTEM_PROMPT

        assert "TfL Explorer" in SYSTEM_PROMPT
        assert "find_nearest_stations" in SYSTEM_PROMPT
        assert "find_route" in SYSTEM_PROMPT
        assert "Big Ben" in SYSTEM_PROMPT


@pytest.mark.unit
class TestRunAgentStream:
    """Test agent streaming function."""

    @pytest.mark.asyncio
    async def test_stream_yields_token_events(self):
        """Should yield token events from agent text responses."""
        mock_memory = AsyncMock()
        mock_memory.save_message = AsyncMock()

        class MockUpdate:
            def __init__(self, text=None, contents=None):
                self.text = text
                self.contents = contents or []

        async def mock_run(msg, stream=True):
            yield MockUpdate(text="Hello ")
            yield MockUpdate(text="London!")

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        with patch("app.agent.record_agent_trace", new_callable=AsyncMock):
            from app.agent import run_agent_stream

            events = []
            async for event in run_agent_stream(mock_agent, "Hi", mock_memory):
                events.append(event)

        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) == 2
        assert json.loads(token_events[0]["data"])["content"] == "Hello "
        assert json.loads(token_events[1]["data"])["content"] == "London!"

    @pytest.mark.asyncio
    async def test_stream_saves_messages(self):
        """Should save user and assistant messages to memory."""
        mock_memory = AsyncMock()
        mock_memory.save_message = AsyncMock()

        class MockUpdate:
            def __init__(self, text=None, contents=None):
                self.text = text
                self.contents = contents or []

        async def mock_run(msg, stream=True):
            yield MockUpdate(text="Response")

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        with patch("app.agent.record_agent_trace", new_callable=AsyncMock):
            from app.agent import run_agent_stream

            async for _ in run_agent_stream(mock_agent, "Hello", mock_memory):
                pass

        calls = mock_memory.save_message.call_args_list
        assert calls[0].args == ("user", "Hello")
        assert calls[1].args == ("assistant", "Response")

    @pytest.mark.asyncio
    async def test_stream_handles_errors(self):
        """Should yield error event on exception."""
        mock_memory = AsyncMock()
        mock_memory.save_message = AsyncMock(side_effect=Exception("DB down"))

        mock_agent = MagicMock()

        from app.agent import run_agent_stream

        events = []
        async for event in run_agent_stream(mock_agent, "Hi", mock_memory):
            events.append(event)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "DB down" in json.loads(error_events[0]["data"])["error"]

    @pytest.mark.asyncio
    async def test_stream_records_reasoning_trace(self):
        """Should call record_agent_trace after successful completion."""
        mock_memory = AsyncMock()
        mock_memory.save_message = AsyncMock()

        class MockUpdate:
            def __init__(self, text=None, contents=None):
                self.text = text
                self.contents = contents or []

        async def mock_run(msg, stream=True):
            yield MockUpdate(text="Done")

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        with patch("app.agent.record_agent_trace", new_callable=AsyncMock) as mock_trace:
            from app.agent import run_agent_stream

            async for _ in run_agent_stream(mock_agent, "Plan route", mock_memory):
                pass

            mock_trace.assert_awaited_once()
            call_kwargs = mock_trace.call_args[1]
            assert call_kwargs["task"] == "Plan route"
            assert call_kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_stream_handles_tool_calls(self):
        """Should yield tool_call and tool_result events."""
        mock_memory = AsyncMock()
        mock_memory.save_message = AsyncMock()

        class MockContent:
            def __init__(self, ctype, **kwargs):
                self.type = ctype
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class MockUpdate:
            def __init__(self, text=None, contents=None):
                self.text = text
                self.contents = contents or []

        async def mock_run(msg, stream=True):
            yield MockUpdate(
                text=None,
                contents=[MockContent("function_call", name="find_route", arguments='{"from": "A"}')],
            )
            yield MockUpdate(
                text=None,
                contents=[MockContent("function_result", call_id="find_route", result='{"path": []}')],
            )
            yield MockUpdate(text="Here's the route.")

        mock_agent = MagicMock()
        mock_agent.run = mock_run

        with patch("app.agent.record_agent_trace", new_callable=AsyncMock):
            from app.agent import run_agent_stream

            events = []
            async for event in run_agent_stream(mock_agent, "Find route", mock_memory):
                events.append(event)

        event_types = [e["event"] for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "token" in event_types
