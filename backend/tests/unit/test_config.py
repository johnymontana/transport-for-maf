"""Unit tests for application configuration."""

from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestSettings:
    """Test Settings loads from environment correctly."""

    def _fresh_settings(self):
        """Reload the config module so os.getenv() defaults are re-evaluated.

        Also patches load_dotenv to prevent .env file from overriding the test env.
        """
        for mod_name in list(sys.modules):
            if mod_name.startswith("app.config"):
                del sys.modules[mod_name]
        from app.config import Settings
        return Settings

    def test_default_settings(self):
        """Settings should have sensible defaults when no env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("dotenv.load_dotenv"):
                Settings = self._fresh_settings()
                s = Settings()
                assert s.neo4j_uri == "bolt://localhost:7687"
                assert s.neo4j_user == "neo4j"
                assert s.neo4j_password == "password"
                assert s.host == "0.0.0.0"
                assert s.port == 8000
                assert "localhost:3000" in s.cors_origins

    def test_settings_from_env(self):
        """Settings should read from env vars."""
        env = {
            "NEO4J_URI": "bolt://custom:7687",
            "NEO4J_USERNAME": "admin",
            "NEO4J_PASSWORD": "secret123",
            "OPENAI_API_KEY": "sk-test",
            "TFL_APP_KEY": "tfl-key-123",
            "BACKEND_PORT": "9000",
            "CORS_ORIGINS": "http://example.com",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("dotenv.load_dotenv"):
                Settings = self._fresh_settings()
                s = Settings()
                assert s.neo4j_uri == "bolt://custom:7687"
                assert s.openai_api_key == "sk-test"
                assert s.tfl_app_key == "tfl-key-123"

    def test_optional_fields_default_none(self):
        """Optional API keys should default to None when not in env."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("dotenv.load_dotenv"):
                Settings = self._fresh_settings()
                s = Settings()
                assert s.tfl_app_key is None
                assert s.openai_api_key is None
                assert s.mapbox_token is None
