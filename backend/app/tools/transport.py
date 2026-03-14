"""Transport tools for the MAF agent.

Provides FunctionTool instances for querying the TfL transport graph
in Neo4j. Each tool returns JSON with graph_data and map_markers
for frontend visualization.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from agent_framework import FunctionTool, tool

from neo4j_agent_memory.integrations.microsoft_agent import Neo4jMicrosoftMemory

from ..tfl_client import TfLClient

logger = logging.getLogger(__name__)


def get_transport_tools(
    memory: Neo4jMicrosoftMemory,
    tfl_client: TfLClient | None = None,
) -> list[FunctionTool]:
    """Create transport tools bound to a memory instance."""
    client = memory.memory_client

    @tool(
        name="find_nearest_stations",
        description=(
            "Find tube/rail stations near a geographic coordinate. "
            "Use when the user asks about stations near a place or location."
        ),
    )
    async def find_nearest_stations(
        lat: Annotated[float, "Latitude of the location"],
        lon: Annotated[float, "Longitude of the location"],
        radius_meters: Annotated[int, "Search radius in meters"] = 1000,
        limit: Annotated[int, "Maximum stations to return"] = 10,
    ) -> str:
        """Find stations near a coordinate using spatial index."""
        cypher = """
        WITH point({latitude: $lat, longitude: $lon}) AS location
        MATCH (s:Station)
        WHERE point.distance(s.location, location) < $radius
        WITH s, round(point.distance(s.location, location)) AS distance
        ORDER BY distance
        LIMIT $limit
        OPTIONAL MATCH (s)-[:ON_LINE]->(l:Line)
        WITH s, distance, collect({lineId: l.lineId, name: l.name, color: l.color}) AS lines
        RETURN s.naptanId AS naptanId, s.name AS name,
               s.lat AS lat, s.lon AS lon, s.zone AS zone,
               distance, lines
        """
        result = await client.graph.execute_read(
            cypher,
            {"lat": lat, "lon": lon, "radius": radius_meters, "limit": limit},
        )

        stations = [dict(r) for r in result]
        nodes = [
            {
                "id": s["naptanId"],
                "label": s["name"],
                "type": "Station",
                "properties": {"lat": s["lat"], "lon": s["lon"], "zone": s["zone"]},
            }
            for s in stations
        ]
        markers = [
            {
                "lat": s["lat"],
                "lon": s["lon"],
                "name": s["name"],
                "type": "station",
                "metadata": {
                    "naptanId": s["naptanId"],
                    "distance": s["distance"],
                    "lines": s["lines"],
                },
            }
            for s in stations
        ]

        return json.dumps({
            "stations": stations,
            "graph_data": {"nodes": nodes, "relationships": []},
            "map_markers": markers,
        })

    @tool(
        name="search_station",
        description=(
            "Search for a station by name. Use when the user mentions "
            "a specific station name."
        ),
    )
    async def search_station(
        name: Annotated[str, "Station name or partial name to search for"],
    ) -> str:
        """Search stations by name."""
        cypher = """
        MATCH (s:Station)
        WHERE toLower(s.name) CONTAINS toLower($name)
        OPTIONAL MATCH (s)-[:ON_LINE]->(l:Line)
        WITH s, collect({lineId: l.lineId, name: l.name, color: l.color}) AS lines
        RETURN s.naptanId AS naptanId, s.name AS name,
               s.lat AS lat, s.lon AS lon, s.zone AS zone, lines
        LIMIT 10
        """
        result = await client.graph.execute_read(cypher, {"name": name})
        stations = [dict(r) for r in result]

        nodes = [
            {
                "id": s["naptanId"],
                "label": s["name"],
                "type": "Station",
                "properties": {"lat": s["lat"], "lon": s["lon"], "zone": s["zone"]},
            }
            for s in stations
        ]
        markers = [
            {
                "lat": s["lat"],
                "lon": s["lon"],
                "name": s["name"],
                "type": "station",
                "metadata": {"naptanId": s["naptanId"], "lines": s["lines"]},
            }
            for s in stations
        ]

        return json.dumps({
            "stations": stations,
            "graph_data": {"nodes": nodes, "relationships": []},
            "map_markers": markers,
        })

    @tool(
        name="get_station_details",
        description=(
            "Get detailed information about a station including connected "
            "lines, nearby bike points, and interchange stations."
        ),
    )
    async def get_station_details(
        station_name: Annotated[str, "Name of the station"],
    ) -> str:
        """Get station details with connections."""
        cypher = """
        MATCH (s:Station)
        WHERE toLower(s.name) CONTAINS toLower($name)
        WITH s LIMIT 1
        OPTIONAL MATCH (s)-[:ON_LINE]->(l:Line)
        WITH s, collect({lineId: l.lineId, name: l.name, color: l.color}) AS lines
        OPTIONAL MATCH (b:BikePoint)-[r:NEAR_STATION]->(s)
        WITH s, lines,
             collect({name: b.name, distance: r.distance,
                      nbBikes: b.nbBikes, nbDocks: b.nbDocks,
                      lat: b.lat, lon: b.lon}) AS bikePoints
        OPTIONAL MATCH (s)-[:INTERCHANGE_WITH]-(other:Station)
        WITH s, lines, bikePoints, collect(other.name) AS interchanges
        OPTIONAL MATCH (s)-[:IN_ZONE]->(z:Zone)
        RETURN s.naptanId AS naptanId, s.name AS name,
               s.lat AS lat, s.lon AS lon, s.zone AS zone,
               z.number AS zoneNumber,
               lines, bikePoints, interchanges
        """
        result = await client.graph.execute_read(cypher, {"name": station_name})

        if not result:
            return json.dumps({"error": f"Station not found: {station_name}"})

        station = dict(result[0])

        # Build graph data with station, lines, and nearby bike points
        nodes = [
            {
                "id": station["naptanId"],
                "label": station["name"],
                "type": "Station",
                "properties": {
                    "lat": station["lat"],
                    "lon": station["lon"],
                    "zone": station["zone"],
                },
            }
        ]
        relationships = []

        for line in station["lines"]:
            nodes.append({
                "id": line["lineId"],
                "label": line["name"],
                "type": "Line",
                "properties": {"color": line["color"]},
            })
            relationships.append({
                "source": station["naptanId"],
                "target": line["lineId"],
                "type": "ON_LINE",
            })

        markers = [
            {
                "lat": station["lat"],
                "lon": station["lon"],
                "name": station["name"],
                "type": "station",
                "metadata": {"naptanId": station["naptanId"]},
            }
        ]
        for bp in station["bikePoints"][:5]:
            markers.append({
                "lat": bp["lat"],
                "lon": bp["lon"],
                "name": bp["name"],
                "type": "bikepoint",
                "metadata": {
                    "nbBikes": bp["nbBikes"],
                    "nbDocks": bp["nbDocks"],
                    "distance": bp["distance"],
                },
            })

        return json.dumps({
            "station": station,
            "graph_data": {"nodes": nodes, "relationships": relationships},
            "map_markers": markers,
        })

    @tool(
        name="find_route",
        description=(
            "Find the shortest route between two stations using the "
            "transport network graph. Returns the sequence of stations."
        ),
    )
    async def find_route(
        from_station: Annotated[str, "Name of the departure station"],
        to_station: Annotated[str, "Name of the destination station"],
    ) -> str:
        """Find shortest route between two stations."""
        cypher = """
        MATCH (start:Station)
        WHERE toLower(start.name) CONTAINS toLower($from)
        WITH start LIMIT 1
        MATCH (end:Station)
        WHERE toLower(end.name) CONTAINS toLower($to)
        WITH start, end LIMIT 1
        MATCH path = shortestPath((start)-[:NEXT_STOP*..50]-(end))
        WITH path, nodes(path) AS stops, relationships(path) AS rels
        UNWIND range(0, size(stops)-1) AS i
        WITH path, stops[i] AS stop, i
        OPTIONAL MATCH (stop)-[:ON_LINE]->(l:Line)
        WITH path, stop, i, collect(DISTINCT l.name) AS lineNames
        ORDER BY i
        RETURN collect({
            naptanId: stop.naptanId,
            name: stop.name,
            lat: stop.lat,
            lon: stop.lon,
            lines: lineNames,
            sequence: i
        }) AS route,
        length(path) AS totalStops
        """
        result = await client.graph.execute_read(
            cypher, {"from": from_station, "to": to_station}
        )

        if not result:
            return json.dumps({
                "error": f"No route found between {from_station} and {to_station}"
            })

        route_data = dict(result[0])
        route = route_data["route"]

        # Build graph nodes and NEXT_STOP edges
        nodes = [
            {
                "id": s["naptanId"],
                "label": s["name"],
                "type": "Station",
                "properties": {"lat": s["lat"], "lon": s["lon"]},
            }
            for s in route
        ]
        relationships = [
            {
                "source": route[i]["naptanId"],
                "target": route[i + 1]["naptanId"],
                "type": "NEXT_STOP",
            }
            for i in range(len(route) - 1)
        ]
        markers = [
            {
                "lat": s["lat"],
                "lon": s["lon"],
                "name": s["name"],
                "type": "route_stop",
                "metadata": {"sequence": s["sequence"], "lines": s["lines"]},
            }
            for s in route
        ]

        return json.dumps({
            "route": route,
            "totalStops": route_data["totalStops"],
            "graph_data": {"nodes": nodes, "relationships": relationships},
            "map_markers": markers,
        })

    @tool(
        name="get_line_stations",
        description=(
            "Get all stations on a specific tube/rail line in order. "
            "Use when the user asks about a specific line."
        ),
    )
    async def get_line_stations(
        line_name: Annotated[str, "Name of the line (e.g., 'Northern', 'Central')"],
    ) -> str:
        """Get all stations on a line."""
        cypher = """
        MATCH (l:Line)
        WHERE toLower(l.name) CONTAINS toLower($name)
        WITH l LIMIT 1
        MATCH (s:Station)-[r:ON_LINE]->(l)
        RETURN s.naptanId AS naptanId, s.name AS name,
               s.lat AS lat, s.lon AS lon, s.zone AS zone,
               r.sequence AS sequence,
               l.lineId AS lineId, l.name AS lineName, l.color AS lineColor
        ORDER BY r.sequence
        """
        result = await client.graph.execute_read(cypher, {"name": line_name})
        stations = [dict(r) for r in result]

        if not stations:
            return json.dumps({"error": f"Line not found: {line_name}"})

        line_info = {
            "lineId": stations[0]["lineId"],
            "name": stations[0]["lineName"],
            "color": stations[0]["lineColor"],
        }

        nodes = [
            {
                "id": s["naptanId"],
                "label": s["name"],
                "type": "Station",
                "properties": {"lat": s["lat"], "lon": s["lon"], "zone": s["zone"]},
            }
            for s in stations
        ]
        nodes.append({
            "id": line_info["lineId"],
            "label": line_info["name"],
            "type": "Line",
            "properties": {"color": line_info["color"]},
        })

        relationships = [
            {
                "source": s["naptanId"],
                "target": line_info["lineId"],
                "type": "ON_LINE",
            }
            for s in stations
        ]
        # Add NEXT_STOP chain
        for i in range(len(stations) - 1):
            relationships.append({
                "source": stations[i]["naptanId"],
                "target": stations[i + 1]["naptanId"],
                "type": "NEXT_STOP",
            })

        markers = [
            {
                "lat": s["lat"],
                "lon": s["lon"],
                "name": s["name"],
                "type": "station",
                "metadata": {"naptanId": s["naptanId"], "zone": s["zone"]},
            }
            for s in stations
        ]

        return json.dumps({
            "line": line_info,
            "stations": stations,
            "graph_data": {"nodes": nodes, "relationships": relationships},
            "map_markers": markers,
        })

    @tool(
        name="find_bike_points",
        description=(
            "Find cycle hire docking stations near a location or tube station. "
            "Returns availability info (bikes and empty docks)."
        ),
    )
    async def find_bike_points(
        lat: Annotated[float, "Latitude of the location"],
        lon: Annotated[float, "Longitude of the location"],
        radius_meters: Annotated[int, "Search radius in meters"] = 500,
        limit: Annotated[int, "Maximum bike points to return"] = 10,
    ) -> str:
        """Find bike points near a location."""
        cypher = """
        WITH point({latitude: $lat, longitude: $lon}) AS location
        MATCH (b:BikePoint)
        WHERE point.distance(b.location, location) < $radius
        WITH b, round(point.distance(b.location, location)) AS distance
        ORDER BY distance
        LIMIT $limit
        RETURN b.id AS id, b.name AS name,
               b.lat AS lat, b.lon AS lon,
               b.nbDocks AS nbDocks, b.nbBikes AS nbBikes,
               b.nbEmptyDocks AS nbEmptyDocks, distance
        """
        result = await client.graph.execute_read(
            cypher,
            {"lat": lat, "lon": lon, "radius": radius_meters, "limit": limit},
        )
        bikepoints = [dict(r) for r in result]

        markers = [
            {
                "lat": bp["lat"],
                "lon": bp["lon"],
                "name": bp["name"],
                "type": "bikepoint",
                "metadata": {
                    "nbBikes": bp["nbBikes"],
                    "nbDocks": bp["nbDocks"],
                    "distance": bp["distance"],
                },
            }
            for bp in bikepoints
        ]

        return json.dumps({
            "bikepoints": bikepoints,
            "graph_data": {"nodes": [], "relationships": []},
            "map_markers": markers,
        })

    @tool(
        name="get_line_status",
        description=(
            "Get the current real-time status of a tube/rail line. "
            "Use when the user asks about delays or service status."
        ),
    )
    async def get_line_status(
        line_name: Annotated[str, "Name of the line (e.g., 'Northern', 'Central')"],
    ) -> str:
        """Get live line status from TfL API."""
        if tfl_client is None:
            return json.dumps({"error": "TfL API client not configured"})

        # First find the line ID
        cypher = """
        MATCH (l:Line)
        WHERE toLower(l.name) CONTAINS toLower($name)
        RETURN l.lineId AS lineId, l.name AS name, l.color AS color
        LIMIT 1
        """
        result = await client.graph.execute_read(cypher, {"name": line_name})
        if not result:
            return json.dumps({"error": f"Line not found: {line_name}"})

        line = dict(result[0])
        status = await tfl_client.get_line_status([line["lineId"]])
        return json.dumps({"line": line, "status": status})

    @tool(
        name="get_disruptions",
        description=(
            "Get current service disruptions across the transport network. "
            "Use when the user asks about problems, delays, or closures."
        ),
    )
    async def get_disruptions() -> str:
        """Get current disruptions from TfL API."""
        if tfl_client is None:
            return json.dumps({"error": "TfL API client not configured"})

        disruptions = await tfl_client.get_disruptions()
        return json.dumps({"disruptions": disruptions})

    @tool(
        name="execute_cypher",
        description=(
            "Execute a read-only Cypher query against the transport graph. "
            "Use for advanced queries that other tools don't cover. "
            "Only MATCH, RETURN, WITH, CALL, UNWIND statements are allowed."
        ),
    )
    async def execute_cypher(
        query: Annotated[str, "Read-only Cypher query to execute"],
    ) -> str:
        """Execute a read-only Cypher query."""
        # Validate read-only
        normalized = query.strip().upper()
        allowed_starts = ("MATCH", "RETURN", "WITH", "CALL", "UNWIND", "OPTIONAL")
        if not normalized.startswith(allowed_starts):
            return json.dumps({
                "error": "Only read-only queries are allowed (MATCH, RETURN, WITH, CALL, UNWIND)"
            })

        forbidden = ("DELETE", "DETACH", "CREATE", "MERGE", "SET ", "REMOVE")
        for word in forbidden:
            if word in normalized:
                return json.dumps({"error": f"Write operations not allowed: {word}"})

        try:
            result = await client.graph.execute_read(query, {})
            records = [dict(r) for r in result]
            return json.dumps({"results": records, "count": len(records)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool(
        name="get_graph_schema",
        description="Get the transport graph schema (node labels, relationship types, and property keys).",
    )
    async def get_graph_schema() -> str:
        """Return the graph schema."""
        schema = {
            "node_labels": {
                "Station": "Transport station with name, location (point), zone, modes",
                "Line": "Tube/rail line with name, modeName, color",
                "BikePoint": "Cycle hire docking station with location, dock counts",
                "Zone": "Travel zone (1-9)",
            },
            "relationship_types": {
                "ON_LINE": "Station is served by a Line (with sequence)",
                "NEXT_STOP": "Sequential connection between stations on a line",
                "IN_ZONE": "Station is in a Zone",
                "INTERCHANGE_WITH": "Stations that are walking-distance interchanges",
                "NEAR_STATION": "BikePoint within 500m of a Station (with distance)",
            },
            "spatial_properties": {
                "Station.location": "point({latitude, longitude})",
                "BikePoint.location": "point({latitude, longitude})",
            },
        }
        return json.dumps(schema)

    return [
        find_nearest_stations,
        search_station,
        get_station_details,
        find_route,
        get_line_stations,
        find_bike_points,
        get_line_status,
        get_disruptions,
        execute_cypher,
        get_graph_schema,
    ]
