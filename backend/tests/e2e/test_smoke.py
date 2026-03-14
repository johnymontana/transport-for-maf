"""End-to-end smoke tests against a running server.

These tests require:
- Backend server running at BACKEND_URL (default http://localhost:8000)
- Neo4j connected and loaded with data
- OPENAI_API_KEY set for chat tests

Run with: pytest tests/e2e/ -m e2e
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _skip_if_no_server():
    """Skip if the backend server isn't running."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip("Backend server not healthy")
    except httpx.ConnectError:
        pytest.skip("Backend server not running")


@pytest.fixture(autouse=True)
def require_server():
    _skip_if_no_server()


@pytest.mark.e2e
class TestHealthSmoke:
    """Verify the server is up and database is connected."""

    def test_health_returns_healthy(self):
        resp = httpx.get(f"{BACKEND_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


@pytest.mark.e2e
class TestStationSmoke:
    """Verify station endpoints return data."""

    def test_get_stations(self):
        resp = httpx.get(f"{BACKEND_URL}/stations", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "stations" in data
        assert len(data["stations"]) > 0

    def test_station_has_coordinates(self):
        resp = httpx.get(f"{BACKEND_URL}/stations", params={"limit": 1})
        station = resp.json()["stations"][0]
        assert "lat" in station
        assert "lon" in station
        assert station["lat"] is not None

    def test_nearby_stations(self):
        """Find stations near Big Ben."""
        resp = httpx.get(
            f"{BACKEND_URL}/stations/nearby",
            params={"lat": 51.5007, "lon": -0.1246, "radius": 1000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stations"]) > 0

    def test_station_details(self):
        """Get details for a known station."""
        # First get a station ID
        resp = httpx.get(f"{BACKEND_URL}/stations", params={"limit": 1})
        station_id = resp.json()["stations"][0]["naptanId"]

        resp = httpx.get(f"{BACKEND_URL}/stations/{station_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["naptanId"] == station_id
        assert "lines" in data


@pytest.mark.e2e
class TestLineSmoke:
    """Verify line endpoints return data."""

    def test_get_lines(self):
        resp = httpx.get(f"{BACKEND_URL}/lines")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["lines"]) > 0

    def test_line_has_color(self):
        resp = httpx.get(f"{BACKEND_URL}/lines")
        line = resp.json()["lines"][0]
        assert "color" in line

    def test_line_stations(self):
        """Get stations for a line."""
        resp = httpx.get(f"{BACKEND_URL}/lines")
        line_id = resp.json()["lines"][0]["lineId"]

        resp = httpx.get(f"{BACKEND_URL}/lines/{line_id}/stations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stations"]) > 0


@pytest.mark.e2e
class TestBikePointSmoke:
    """Verify bike point endpoints."""

    def test_nearby_bikepoints(self):
        resp = httpx.get(
            f"{BACKEND_URL}/bikepoints/nearby",
            params={"lat": 51.5074, "lon": -0.1278, "radius": 1000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "bikepoints" in data


@pytest.mark.e2e
class TestGraphNeighborhoodSmoke:
    """Verify graph expansion endpoint."""

    def test_expand_station(self):
        """Expand a station node's neighborhood."""
        # Get a station ID first
        resp = httpx.get(f"{BACKEND_URL}/stations", params={"limit": 1})
        station_id = resp.json()["stations"][0]["naptanId"]

        resp = httpx.get(f"{BACKEND_URL}/graph/neighborhood/{station_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "center" in data
        assert "nodes" in data
        assert "relationships" in data


@pytest.mark.e2e
class TestChatSmoke:
    """Smoke test the chat endpoint (requires OPENAI_API_KEY)."""

    @pytest.fixture(autouse=True)
    def require_openai(self):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

    def test_sync_chat(self):
        """POST /chat/sync should return a response."""
        resp = httpx.post(
            f"{BACKEND_URL}/chat/sync",
            json={"message": "What stations are near Big Ben?", "session_id": "e2e-test"},
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["response"]) > 0
        assert data["session_id"] == "e2e-test"

    def test_sse_chat_stream(self):
        """POST /chat should stream SSE events."""
        with httpx.stream(
            "POST",
            f"{BACKEND_URL}/chat",
            json={"message": "Hello", "session_id": "e2e-test-stream"},
            timeout=60,
        ) as resp:
            assert resp.status_code == 200
            events = []
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
            # Should have at least a token event and done event
            assert "done" in events or len(events) > 0


@pytest.mark.e2e
class TestMemorySmoke:
    """Verify memory endpoints respond."""

    def test_memory_context(self):
        resp = httpx.get(
            f"{BACKEND_URL}/memory/context",
            params={"session_id": "e2e-smoke"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "short_term" in data

    def test_memory_preferences(self):
        resp = httpx.get(
            f"{BACKEND_URL}/memory/preferences",
            params={"session_id": "e2e-smoke"},
        )
        assert resp.status_code == 200
        assert "preferences" in resp.json()
