"""Unit tests for memory_setup module."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestGetMemorySettings:
    """Test get_memory_settings produces correct MemorySettings."""

    def test_settings_created_from_env(self):
        """MemorySettings should reflect app config."""
        with patch.dict(os.environ, {
            "NEO4J_URI": "bolt://mem:7687",
            "NEO4J_USERNAME": "memuser",
            "NEO4J_PASSWORD": "mempass",
            "OPENAI_API_KEY": "sk-test-mem",
        }, clear=False):
            # Reimport to pick up env
            from importlib import reload
            from app import config as cfg_mod

            reload(cfg_mod)
            from app.memory_setup import get_memory_settings

            ms = get_memory_settings()
            # MemorySettings should have neo4j and embedding sections
            assert ms is not None


@pytest.mark.unit
class TestMemoryClientLifecycle:
    """Test init/close/get memory client helpers."""

    @pytest.mark.asyncio
    async def test_init_and_get_memory_client(self):
        """init_memory_client should set the global client."""
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()

        with patch("app.memory_setup.MemoryClient", return_value=mock_client):
            with patch("app.memory_setup.get_memory_settings"):
                from app.memory_setup import (
                    close_memory_client,
                    get_memory_client,
                    init_memory_client,
                )
                import app.memory_setup as ms_mod

                await init_memory_client()
                mock_client.connect.assert_awaited_once()

                client = get_memory_client()
                assert client is mock_client

                # Cleanup
                mock_client.close = AsyncMock()
                await close_memory_client()
                mock_client.close.assert_awaited_once()
                assert ms_mod.memory_client is None

    def test_get_memory_client_raises_when_not_initialized(self):
        """get_memory_client should raise RuntimeError before init."""
        import app.memory_setup as ms_mod

        original = ms_mod.memory_client
        try:
            ms_mod.memory_client = None
            with pytest.raises(RuntimeError, match="not initialized"):
                ms_mod.get_memory_client()
        finally:
            ms_mod.memory_client = original


@pytest.mark.unit
class TestCreateMemory:
    """Test create_memory factory."""

    @pytest.mark.asyncio
    async def test_create_memory_returns_neo4j_microsoft_memory(self):
        """create_memory should return a Neo4jMicrosoftMemory instance."""
        mock_client = MagicMock()
        mock_memory = MagicMock()

        with patch("app.memory_setup.get_memory_client", return_value=mock_client):
            with patch(
                "app.memory_setup.Neo4jMicrosoftMemory",
                return_value=mock_memory,
            ) as mock_cls:
                from app.memory_setup import create_memory

                result = await create_memory("session-1", "user-1")

                assert result is mock_memory
                call_kwargs = mock_cls.call_args[1]
                assert call_kwargs["memory_client"] is mock_client
                assert call_kwargs["session_id"] == "session-1"
                assert call_kwargs["user_id"] == "user-1"
                assert call_kwargs["include_short_term"] is True
                assert call_kwargs["include_long_term"] is True
                assert call_kwargs["include_reasoning"] is True
                assert call_kwargs["extract_entities"] is True
                assert call_kwargs["extract_entities_async"] is True
                # v0.1.0: GDS config should be passed
                assert call_kwargs["gds_config"] is not None
                assert call_kwargs["gds_config"].enabled is True
                assert call_kwargs["gds_config"].fallback_to_basic is True

    @pytest.mark.asyncio
    async def test_create_memory_default_user_id(self):
        """create_memory should accept None user_id."""
        mock_client = MagicMock()
        mock_memory = MagicMock()

        with patch("app.memory_setup.get_memory_client", return_value=mock_client):
            with patch(
                "app.memory_setup.Neo4jMicrosoftMemory",
                return_value=mock_memory,
            ) as mock_cls:
                from app.memory_setup import create_memory

                result = await create_memory("session-2")
                assert result is mock_memory
                # user_id should be None
                call_kwargs = mock_cls.call_args[1]
                assert call_kwargs["user_id"] is None
