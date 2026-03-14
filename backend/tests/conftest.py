"""Root conftest with shared fixtures for all test tiers."""

from __future__ import annotations

import hashlib
import json
import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers – lightweight mocks used across unit *and* integration tests
# ---------------------------------------------------------------------------


class MockGraphExecutor:
    """Fake `client.graph` that returns canned query results."""

    def __init__(self, results: list[dict] | None = None):
        self._results = results or []

    async def execute_read(self, query: str, params: dict | None = None) -> list[dict]:
        return self._results

    async def execute_write(self, query: str, params: dict | None = None) -> list[dict]:
        return self._results


class MockEmbedder:
    """Deterministic embedder for testing (no OpenAI calls)."""

    dimensions = 256

    async def embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).hexdigest()
        return [
            float(int(h[i : i + 2], 16)) / 255.0
            for i in range(0, min(len(h), self.dimensions * 2), 2)
        ]


class MockMemoryClient:
    """Minimal mock of neo4j_agent_memory.MemoryClient for unit tests."""

    def __init__(self, graph_results: list[dict] | None = None):
        self.graph = MockGraphExecutor(graph_results)
        self._embedder = MockEmbedder()
        self.is_connected = True
        self.short_term = AsyncMock()
        self.long_term = AsyncMock()
        self.reasoning = AsyncMock()

        # Sensible defaults for search methods
        self.short_term.get_conversation = AsyncMock(
            return_value=MagicMock(messages=[])
        )
        self.short_term.search_messages = AsyncMock(return_value=[])
        self.short_term.add_message = AsyncMock()
        self.long_term.search_entities = AsyncMock(return_value=[])
        self.long_term.search_preferences = AsyncMock(return_value=[])
        self.long_term.add_preference = AsyncMock()
        self.long_term.add_fact = AsyncMock()
        self.reasoning.get_similar_traces = AsyncMock(return_value=[])

    async def connect(self):
        pass

    async def close(self):
        pass


class MockMemory:
    """Minimal mock of Neo4jMicrosoftMemory."""

    def __init__(self, memory_client: MockMemoryClient | None = None):
        self.memory_client = memory_client or MockMemoryClient()
        self.context_provider = MagicMock()
        self.gds = None
        self._session_id = f"test-{uuid4()}"

    @property
    def session_id(self):
        return self._session_id

    async def save_message(self, role: str, content: str, **kwargs):
        pass

    async def search_memory(self, query, **kwargs):
        return {"messages": [], "entities": [], "preferences": []}

    async def add_preference(self, category, preference, context=None):
        pass

    async def add_fact(self, subject, predicate, obj):
        pass

    async def get_similar_traces(self, task, limit=5):
        return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session_id() -> str:
    return f"test-session-{uuid4()}"


@pytest.fixture
def mock_memory_client() -> MockMemoryClient:
    return MockMemoryClient()


@pytest.fixture
def mock_memory(mock_memory_client) -> MockMemory:
    return MockMemory(mock_memory_client)


@pytest.fixture
def sample_stations() -> list[dict]:
    """Sample station data mimicking TfL API response."""
    return [
        {
            "naptanId": "940GZZLUWLO",
            "commonName": "Waterloo Underground Station",
            "lat": 51.5031,
            "lon": -0.1132,
            "modes": ["tube"],
            "zone": "1",
            "lines": [
                {"id": "bakerloo", "name": "Bakerloo"},
                {"id": "jubilee", "name": "Jubilee"},
                {"id": "northern", "name": "Northern"},
                {"id": "waterloo-city", "name": "Waterloo & City"},
            ],
        },
        {
            "naptanId": "940GZZLUKSX",
            "commonName": "King's Cross St. Pancras Underground Station",
            "lat": 51.5308,
            "lon": -0.1238,
            "modes": ["tube"],
            "zone": "1",
            "lines": [
                {"id": "circle", "name": "Circle"},
                {"id": "hammersmith-city", "name": "Hammersmith & City"},
                {"id": "metropolitan", "name": "Metropolitan"},
                {"id": "northern", "name": "Northern"},
                {"id": "piccadilly", "name": "Piccadilly"},
                {"id": "victoria", "name": "Victoria"},
            ],
        },
        {
            "naptanId": "940GZZLUBXN",
            "commonName": "Brixton Underground Station",
            "lat": 51.4627,
            "lon": -0.1145,
            "modes": ["tube"],
            "zone": "2",
            "lines": [{"id": "victoria", "name": "Victoria"}],
        },
    ]


@pytest.fixture
def sample_lines() -> list[dict]:
    """Sample line data."""
    return [
        {"id": "northern", "name": "Northern", "modeName": "tube", "color": "#000000"},
        {"id": "victoria", "name": "Victoria", "modeName": "tube", "color": "#0098D4"},
        {"id": "bakerloo", "name": "Bakerloo", "modeName": "tube", "color": "#B36305"},
    ]


@pytest.fixture
def sample_bikepoints() -> list[dict]:
    """Sample bike point data."""
    return [
        {
            "id": "BikePoints_1",
            "commonName": "River Street, Clerkenwell",
            "lat": 51.5292,
            "lon": -0.1099,
            "nbDocks": 19,
            "nbBikes": 12,
            "nbEmptyDocks": 7,
        },
        {
            "id": "BikePoints_2",
            "commonName": "Phillimore Gardens, Kensington",
            "lat": 51.4994,
            "lon": -0.1973,
            "nbDocks": 37,
            "nbBikes": 22,
            "nbEmptyDocks": 15,
        },
    ]


# ---------------------------------------------------------------------------
# Neo4j integration fixtures (skip when unavailable)
# ---------------------------------------------------------------------------


def _check_neo4j_env() -> dict | None:
    """Check if Neo4j is available via environment variables."""
    uri = os.getenv("NEO4J_URI")
    if not uri:
        return None
    return {
        "uri": uri,
        "username": os.getenv("NEO4J_USERNAME", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", "password"),
    }


@pytest.fixture(scope="session")
def neo4j_config():
    """Provide Neo4j connection config, from env or testcontainers."""
    # Try env first
    env_config = _check_neo4j_env()
    if env_config:
        yield env_config
        return

    # Try testcontainers
    try:
        from testcontainers.neo4j import Neo4jContainer

        container = Neo4jContainer("neo4j:5-community")
        container.with_env("NEO4J_PLUGINS", '["apoc"]')
        container.start()
        yield {
            "uri": container.get_connection_url(),
            "username": "neo4j",
            "password": container.password,
        }
        container.stop()
    except Exception:
        pytest.skip("Neo4j not available (no env vars, no testcontainers)")


@pytest.fixture
async def neo4j_driver(neo4j_config):
    """Create and yield an async Neo4j driver, clean up after."""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        neo4j_config["uri"],
        auth=(neo4j_config["username"], neo4j_config["password"]),
    )
    yield driver
    # Cleanup all test data
    async with driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    await driver.close()
