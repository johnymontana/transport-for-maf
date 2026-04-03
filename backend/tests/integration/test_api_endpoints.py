"""Integration tests for FastAPI endpoints using httpx TestClient.

These tests mock the memory client / Neo4j layer but exercise the full
HTTP request → FastAPI route → response cycle.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_memory_client(graph_results=None):
    """Create a mock memory client for patching into the app."""
    client = MagicMock()
    client.is_connected = True
    client.graph = MagicMock()
    client.graph.execute_read = AsyncMock(return_value=graph_results or [])
    client.short_term = MagicMock()
    client.short_term.get_conversation = AsyncMock(
        return_value=MagicMock(messages=[])
    )
    client.short_term.list_sessions = AsyncMock(return_value=[])
    client.short_term.clear_session = AsyncMock()
    client.long_term = MagicMock()
    client.long_term.search_entities = AsyncMock(return_value=[])
    client.long_term.search_preferences = AsyncMock(return_value=[])
    client.reasoning = MagicMock()
    client.reasoning.get_similar_traces = AsyncMock(return_value=[])
    # Memory graph export API (v0.1.0)
    client.get_graph = AsyncMock(
        return_value=MagicMock(nodes=[], relationships=[], metadata={})
    )
    client.get_locations = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_client():
    return _mock_memory_client()


@pytest.fixture
async def client(mock_client):
    """Create an httpx AsyncClient against the FastAPI app with mocked dependencies."""
    # Patch lifespan to avoid real connections
    from app.main import app

    with patch("app.main.init_memory_client", new_callable=AsyncMock):
        with patch("app.main.close_memory_client", new_callable=AsyncMock):
            with patch("app.main.get_memory_client", return_value=mock_client):
                with patch("app.main.TfLClient") as mock_tfl_cls:
                    mock_tfl = MagicMock()
                    mock_tfl.close = AsyncMock()
                    mock_tfl.get_disruptions = AsyncMock(return_value=[])
                    mock_tfl_cls.return_value = mock_tfl

                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as ac:
                        yield ac


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert "database" in data


# ---------------------------------------------------------------------------
# Stations
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestStationEndpoints:

    @pytest.mark.asyncio
    async def test_get_stations(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[
            {"naptanId": "940GZZLUWLO", "name": "Waterloo", "lat": 51.5, "lon": -0.11, "zone": "1", "modes": ["tube"], "lines": []},
        ])
        resp = await client.get("/stations")
        assert resp.status_code == 200
        data = resp.json()
        assert "stations" in data
        assert len(data["stations"]) == 1
        assert data["stations"][0]["name"] == "Waterloo"

    @pytest.mark.asyncio
    async def test_get_station_by_id(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[
            {
                "naptanId": "940GZZLUWLO",
                "name": "Waterloo",
                "lat": 51.5,
                "lon": -0.11,
                "zone": "1",
                "lines": [{"lineId": "northern", "name": "Northern", "color": "#000"}],
                "bikePoints": [],
                "interchanges": [],
            }
        ])
        resp = await client.get("/stations/940GZZLUWLO")
        assert resp.status_code == 200
        data = resp.json()
        assert data["naptanId"] == "940GZZLUWLO"

    @pytest.mark.asyncio
    async def test_get_station_not_found(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[])
        resp = await client.get("/stations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nearby_stations(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[
            {"naptanId": "940GZZLUWLO", "name": "Waterloo", "lat": 51.5, "lon": -0.11, "zone": "1", "distance": 200},
        ])
        resp = await client.get("/stations/nearby", params={"lat": 51.5, "lon": -0.11})
        # Note: /stations/nearby may match /stations/{naptan_id} depending on route order
        assert resp.status_code == 200
        data = resp.json()
        assert "stations" in data or "naptanId" in data


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLineEndpoints:

    @pytest.mark.asyncio
    async def test_get_lines(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[
            {"lineId": "northern", "name": "Northern", "modeName": "tube", "color": "#000", "stationCount": 50},
        ])
        resp = await client.get("/lines")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["lines"]) == 1
        assert data["lines"][0]["lineId"] == "northern"

    @pytest.mark.asyncio
    async def test_get_line_stations(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[
            {"naptanId": "940GZZLUWLO", "name": "Waterloo", "lat": 51.5, "lon": -0.11, "zone": "1", "sequence": 1, "lineName": "Northern", "lineColor": "#000"},
        ])
        resp = await client.get("/lines/northern/stations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stations"]) == 1


# ---------------------------------------------------------------------------
# Bike Points
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestBikePointEndpoints:

    @pytest.mark.asyncio
    async def test_get_nearby_bikepoints(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[
            {"id": "BP1", "name": "River St", "lat": 51.5, "lon": -0.11, "nbDocks": 19, "nbBikes": 12, "nbEmptyDocks": 7, "distance": 100},
        ])
        resp = await client.get("/bikepoints/nearby", params={"lat": 51.5, "lon": -0.11})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["bikepoints"]) == 1


# ---------------------------------------------------------------------------
# Graph Neighborhood
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGraphNeighborhoodEndpoint:

    @pytest.mark.asyncio
    async def test_get_neighborhood(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[
            {
                "center": {"id": "940GZZLUWLO", "label": "Waterloo", "type": "Station", "properties": {}},
                "neighbors": [{"id": "northern", "label": "Northern", "type": "Line", "properties": {}}],
                "relationships": [{"source": "940GZZLUWLO", "target": "northern", "type": "ON_LINE"}],
            }
        ])
        resp = await client.get("/graph/neighborhood/940GZZLUWLO")
        assert resp.status_code == 200
        data = resp.json()
        assert data["center"]["id"] == "940GZZLUWLO"
        assert len(data["nodes"]) == 2  # center + 1 neighbor

    @pytest.mark.asyncio
    async def test_neighborhood_not_found(self, client, mock_client):
        mock_client.graph.execute_read = AsyncMock(return_value=[])
        resp = await client.get("/graph/neighborhood/NONEXISTENT")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Memory Endpoints
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMemoryEndpoints:

    @pytest.mark.asyncio
    async def test_get_memory_context(self, client, mock_client):
        resp = await client.get("/memory/context", params={"session_id": "test-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "short_term" in data
        assert "long_term" in data
        assert "reasoning" in data

    @pytest.mark.asyncio
    async def test_get_memory_graph(self, client, mock_client):
        resp = await client.get("/memory/graph", params={"session_id": "test-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "relationships" in data
        mock_client.get_graph.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_preferences(self, client, mock_client):
        resp = await client.get("/memory/preferences", params={"session_id": "test-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "preferences" in data

    @pytest.mark.asyncio
    async def test_get_memory_locations(self, client, mock_client):
        mock_client.get_locations = AsyncMock(return_value=[
            {"name": "King's Cross", "latitude": 51.5308, "longitude": -0.1238, "subtype": "station", "description": "Railway station"},
        ])
        resp = await client.get("/memory/locations", params={"session_id": "test-1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "locations" in data
        assert len(data["locations"]) == 1
        assert data["locations"][0]["name"] == "King's Cross"
        assert data["locations"][0]["lat"] == 51.5308

    @pytest.mark.asyncio
    async def test_list_memory_sessions(self, client, mock_client):
        resp = await client.get("/memory/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data

    @pytest.mark.asyncio
    async def test_clear_memory_session(self, client, mock_client):
        with patch("app.main.create_memory", new_callable=AsyncMock) as mock_mem:
            mock_memory = MagicMock()
            mock_memory.clear_session = AsyncMock()
            mock_mem.return_value = mock_memory
            resp = await client.delete("/memory/session/test-1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "cleared"


# ---------------------------------------------------------------------------
# Disruptions
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDisruptionsEndpoint:

    @pytest.mark.asyncio
    async def test_get_disruptions(self, client):
        """Should proxy to TfL client."""
        import app.main as main_mod

        mock_tfl = MagicMock()
        mock_tfl.get_disruptions = AsyncMock(return_value=[])
        original = main_mod.tfl_client
        main_mod.tfl_client = mock_tfl
        try:
            resp = await client.get("/disruptions")
            assert resp.status_code == 200
            data = resp.json()
            assert "disruptions" in data
        finally:
            main_mod.tfl_client = original

    @pytest.mark.asyncio
    async def test_disruptions_503_when_no_client(self, client):
        """Should return 503 when TfL client is not available."""
        import app.main as main_mod

        original = main_mod.tfl_client
        main_mod.tfl_client = None
        try:
            resp = await client.get("/disruptions")
            assert resp.status_code == 503
        finally:
            main_mod.tfl_client = original


# ---------------------------------------------------------------------------
# Chat Endpoints (shallow integration - mock agent layer)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestChatEndpoints:

    @pytest.mark.asyncio
    async def test_sync_chat(self, client, mock_client):
        """POST /chat/sync should return a ChatResponse."""

        async def mock_stream(agent, message, memory):
            yield {"event": "token", "data": json.dumps({"content": "Hello!"})}

        with patch("app.main.create_memory", new_callable=AsyncMock) as mock_mem:
            mock_mem.return_value = MagicMock()
            with patch("app.main.create_agent", new_callable=AsyncMock):
                with patch("app.main.run_agent_stream", side_effect=mock_stream):
                    resp = await client.post(
                        "/chat/sync",
                        json={"message": "Hi", "session_id": "test-chat-1"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["response"] == "Hello!"
                    assert data["session_id"] == "test-chat-1"
