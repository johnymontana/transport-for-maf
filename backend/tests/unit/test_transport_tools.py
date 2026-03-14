"""Unit tests for transport tools.

Tools are tested with a MockMemoryClient that returns canned Neo4j results.
No real database connection needed.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import MockMemoryClient, MockMemory


def _make_memory_with_results(results: list[dict]) -> MockMemory:
    """Create a MockMemory whose graph.execute_read returns the given results."""
    mc = MockMemoryClient(graph_results=results)
    return MockMemory(mc)


@pytest.mark.unit
class TestFindNearestStations:
    """Test the find_nearest_stations tool."""

    @pytest.mark.asyncio
    async def test_returns_stations_sorted_by_distance(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {
                "naptanId": "940GZZLUWLO",
                "name": "Waterloo Underground Station",
                "lat": 51.5031,
                "lon": -0.1132,
                "zone": "1",
                "distance": 150,
                "lines": [{"lineId": "bakerloo", "name": "Bakerloo", "color": "#B36305"}],
            },
            {
                "naptanId": "940GZZLUSBC",
                "name": "Southwark Underground Station",
                "lat": 51.5040,
                "lon": -0.1050,
                "zone": "1",
                "distance": 400,
                "lines": [{"lineId": "jubilee", "name": "Jubilee", "color": "#A0A5A9"}],
            },
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)

        # Find the tool by name
        find_nearest = next(t for t in tools if t.name == "find_nearest_stations")
        result_str = await find_nearest(lat=51.5033, lon=-0.1195, radius_meters=1000, limit=10)
        result = json.loads(result_str)

        assert "stations" in result
        assert len(result["stations"]) == 2
        assert result["stations"][0]["naptanId"] == "940GZZLUWLO"
        assert result["stations"][0]["distance"] == 150

    @pytest.mark.asyncio
    async def test_returns_map_markers(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {
                "naptanId": "940GZZLUWLO",
                "name": "Waterloo",
                "lat": 51.5031,
                "lon": -0.1132,
                "zone": "1",
                "distance": 150,
                "lines": [],
            },
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        find_nearest = next(t for t in tools if t.name == "find_nearest_stations")

        result = json.loads(await find_nearest(lat=51.5, lon=-0.1))
        assert "map_markers" in result
        assert len(result["map_markers"]) == 1
        assert result["map_markers"][0]["type"] == "station"
        assert result["map_markers"][0]["lat"] == 51.5031

    @pytest.mark.asyncio
    async def test_returns_graph_data(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {
                "naptanId": "940GZZLUWLO",
                "name": "Waterloo",
                "lat": 51.5031,
                "lon": -0.1132,
                "zone": "1",
                "distance": 150,
                "lines": [],
            },
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        find_nearest = next(t for t in tools if t.name == "find_nearest_stations")

        result = json.loads(await find_nearest(lat=51.5, lon=-0.1))
        assert "graph_data" in result
        assert result["graph_data"]["nodes"][0]["type"] == "Station"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        find_nearest = next(t for t in tools if t.name == "find_nearest_stations")

        result = json.loads(await find_nearest(lat=0, lon=0, radius_meters=1))
        assert result["stations"] == []
        assert result["map_markers"] == []


@pytest.mark.unit
class TestSearchStation:
    """Test the search_station tool."""

    @pytest.mark.asyncio
    async def test_search_by_name(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {
                "naptanId": "940GZZLUWLO",
                "name": "Waterloo Underground Station",
                "lat": 51.5031,
                "lon": -0.1132,
                "zone": "1",
                "lines": [{"lineId": "northern", "name": "Northern", "color": "#000000"}],
            },
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        search = next(t for t in tools if t.name == "search_station")

        result = json.loads(await search(name="Waterloo"))
        assert len(result["stations"]) == 1
        assert result["stations"][0]["name"] == "Waterloo Underground Station"


@pytest.mark.unit
class TestGetStationDetails:
    """Test the get_station_details tool."""

    @pytest.mark.asyncio
    async def test_returns_full_details(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {
                "naptanId": "940GZZLUWLO",
                "name": "Waterloo Underground Station",
                "lat": 51.5031,
                "lon": -0.1132,
                "zone": "1",
                "zoneNumber": "1",
                "lines": [
                    {"lineId": "bakerloo", "name": "Bakerloo", "color": "#B36305"},
                    {"lineId": "northern", "name": "Northern", "color": "#000000"},
                ],
                "bikePoints": [
                    {"name": "Waterloo Bike Station", "distance": 100, "nbBikes": 8, "nbDocks": 20, "lat": 51.503, "lon": -0.113},
                ],
                "interchanges": ["Waterloo East"],
            },
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        detail = next(t for t in tools if t.name == "get_station_details")

        result = json.loads(await detail(station_name="Waterloo"))
        assert result["station"]["naptanId"] == "940GZZLUWLO"
        assert len(result["station"]["lines"]) == 2
        assert len(result["station"]["bikePoints"]) == 1

        # Should have graph data with station + line nodes
        nodes = result["graph_data"]["nodes"]
        assert any(n["type"] == "Station" for n in nodes)
        assert any(n["type"] == "Line" for n in nodes)

    @pytest.mark.asyncio
    async def test_station_not_found(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        detail = next(t for t in tools if t.name == "get_station_details")

        result = json.loads(await detail(station_name="Nonexistent"))
        assert "error" in result


@pytest.mark.unit
class TestFindRoute:
    """Test the find_route tool."""

    @pytest.mark.asyncio
    async def test_route_found(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {
                "route": [
                    {"naptanId": "A", "name": "Station A", "lat": 51.5, "lon": -0.1, "lines": ["Northern"], "sequence": 0},
                    {"naptanId": "B", "name": "Station B", "lat": 51.51, "lon": -0.11, "lines": ["Northern"], "sequence": 1},
                    {"naptanId": "C", "name": "Station C", "lat": 51.52, "lon": -0.12, "lines": ["Northern"], "sequence": 2},
                ],
                "totalStops": 2,
            },
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        route = next(t for t in tools if t.name == "find_route")

        result = json.loads(await route(from_station="Station A", to_station="Station C"))
        assert result["totalStops"] == 2
        assert len(result["route"]) == 3

        # Graph data should have NEXT_STOP relationships
        rels = result["graph_data"]["relationships"]
        assert all(r["type"] == "NEXT_STOP" for r in rels)
        assert len(rels) == 2  # A->B, B->C

        # Map markers for route
        assert len(result["map_markers"]) == 3
        assert all(m["type"] == "route_stop" for m in result["map_markers"])

    @pytest.mark.asyncio
    async def test_route_not_found(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        route = next(t for t in tools if t.name == "find_route")

        result = json.loads(await route(from_station="X", to_station="Y"))
        assert "error" in result


@pytest.mark.unit
class TestGetLineStations:
    """Test the get_line_stations tool."""

    @pytest.mark.asyncio
    async def test_returns_stations_in_order(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {"naptanId": "A", "name": "Morden", "lat": 51.4, "lon": -0.19, "zone": "4", "sequence": 0, "lineId": "northern", "lineName": "Northern", "lineColor": "#000000"},
            {"naptanId": "B", "name": "South Wimbledon", "lat": 51.41, "lon": -0.19, "zone": "3", "sequence": 1, "lineId": "northern", "lineName": "Northern", "lineColor": "#000000"},
            {"naptanId": "C", "name": "Colliers Wood", "lat": 51.42, "lon": -0.18, "zone": "3", "sequence": 2, "lineId": "northern", "lineName": "Northern", "lineColor": "#000000"},
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        line_stations = next(t for t in tools if t.name == "get_line_stations")

        result = json.loads(await line_stations(line_name="Northern"))
        assert result["line"]["name"] == "Northern"
        assert result["line"]["color"] == "#000000"
        assert len(result["stations"]) == 3
        assert result["stations"][0]["name"] == "Morden"

    @pytest.mark.asyncio
    async def test_line_not_found(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        line_stations = next(t for t in tools if t.name == "get_line_stations")

        result = json.loads(await line_stations(line_name="Fake"))
        assert "error" in result


@pytest.mark.unit
class TestFindBikePoints:
    """Test the find_bike_points tool."""

    @pytest.mark.asyncio
    async def test_returns_bikepoints(self):
        from app.tools.transport import get_transport_tools

        graph_results = [
            {
                "id": "BP1",
                "name": "Waterloo Station Bike Point",
                "lat": 51.5031,
                "lon": -0.1132,
                "nbDocks": 30,
                "nbBikes": 15,
                "nbEmptyDocks": 15,
                "distance": 120,
            },
        ]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        find_bp = next(t for t in tools if t.name == "find_bike_points")

        result = json.loads(await find_bp(lat=51.5, lon=-0.1))
        assert len(result["bikepoints"]) == 1
        assert result["bikepoints"][0]["nbBikes"] == 15
        assert result["map_markers"][0]["type"] == "bikepoint"


@pytest.mark.unit
class TestExecuteCypher:
    """Test the execute_cypher tool."""

    @pytest.mark.asyncio
    async def test_valid_read_query(self):
        from app.tools.transport import get_transport_tools

        graph_results = [{"count": 42}]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory)
        cypher = next(t for t in tools if t.name == "execute_cypher")

        result = json.loads(await cypher(query="MATCH (s:Station) RETURN count(s) AS count"))
        assert result["results"][0]["count"] == 42

    @pytest.mark.asyncio
    async def test_rejects_write_query_create(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        cypher = next(t for t in tools if t.name == "execute_cypher")

        result = json.loads(await cypher(query="CREATE (n:Node {name: 'test'})"))
        assert "error" in result
        assert "error" in result  # error message about read-only

    @pytest.mark.asyncio
    async def test_rejects_write_query_delete(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        cypher = next(t for t in tools if t.name == "execute_cypher")

        result = json.loads(await cypher(query="MATCH (n) DELETE n"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_merge(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        cypher = next(t for t in tools if t.name == "execute_cypher")

        result = json.loads(await cypher(query="MERGE (n:Node {name: 'test'})"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rejects_set(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        cypher = next(t for t in tools if t.name == "execute_cypher")

        result = json.loads(await cypher(query="MATCH (n) SET n.x = 1 RETURN n"))
        assert "error" in result


@pytest.mark.unit
class TestGetGraphSchema:
    """Test the get_graph_schema tool."""

    @pytest.mark.asyncio
    async def test_returns_schema(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        schema = next(t for t in tools if t.name == "get_graph_schema")

        result = json.loads(await schema())
        assert "node_labels" in result
        assert "relationship_types" in result
        assert "spatial_properties" in result
        assert "Station" in result["node_labels"]
        assert "NEXT_STOP" in result["relationship_types"]


@pytest.mark.unit
class TestGetLineStatus:
    """Test the get_line_status tool."""

    @pytest.mark.asyncio
    async def test_no_tfl_client(self):
        """Should return error when TfL client is None."""
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory, tfl_client=None)
        status = next(t for t in tools if t.name == "get_line_status")

        result = json.loads(await status(line_name="Northern"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_with_tfl_client(self):
        """Should query TfL API when client is available."""
        from unittest.mock import AsyncMock
        from app.tools.transport import get_transport_tools

        # Mock TfL client
        tfl = MagicMock()
        tfl.get_line_status = AsyncMock(return_value=[{"lineId": "northern", "statuses": []}])

        # Mock graph to find line ID
        graph_results = [{"lineId": "northern", "name": "Northern", "color": "#000000"}]
        memory = _make_memory_with_results(graph_results)
        tools = get_transport_tools(memory, tfl_client=tfl)
        status = next(t for t in tools if t.name == "get_line_status")

        result = json.loads(await status(line_name="Northern"))
        assert result["line"]["lineId"] == "northern"
        tfl.get_line_status.assert_called_once()


@pytest.mark.unit
class TestGetDisruptions:
    """Test the get_disruptions tool."""

    @pytest.mark.asyncio
    async def test_no_tfl_client(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory, tfl_client=None)
        disrupt = next(t for t in tools if t.name == "get_disruptions")

        result = json.loads(await disrupt())
        assert "error" in result


@pytest.mark.unit
class TestToolRegistration:
    """Verify all expected tools are registered."""

    @pytest.mark.asyncio
    async def test_all_tools_present(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        names = {t.name for t in tools}

        expected = {
            "find_nearest_stations",
            "search_station",
            "get_station_details",
            "find_route",
            "get_line_stations",
            "find_bike_points",
            "get_line_status",
            "get_disruptions",
            "execute_cypher",
            "get_graph_schema",
        }
        assert names == expected

    @pytest.mark.asyncio
    async def test_tools_count(self):
        from app.tools.transport import get_transport_tools

        memory = _make_memory_with_results([])
        tools = get_transport_tools(memory)
        assert len(tools) == 10
