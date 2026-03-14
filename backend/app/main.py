"""FastAPI server for TfL Explorer.

Provides:
- SSE streaming for chat responses
- Memory context and graph visualization endpoints
- Transport data REST endpoints
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .agent import create_agent, run_agent_stream
from .config import settings
from .memory_setup import (
    close_memory_client,
    create_memory,
    get_memory_client,
    init_memory_client,
)
from .tfl_client import TfLClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global TfL client
tfl_client: TfLClient | None = None

# In-memory session store
sessions: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global tfl_client

    # Startup
    logger.info("Starting TfL Explorer backend...")
    await init_memory_client()
    tfl_client = TfLClient(app_key=settings.tfl_app_key)
    logger.info("Backend ready.")

    yield

    # Shutdown
    if tfl_client:
        await tfl_client.close()
    await close_memory_client()
    logger.info("Backend shut down.")


app = FastAPI(
    title="TfL Explorer API",
    description="London transport assistant powered by Microsoft Agent Framework and Neo4j Agent Memory",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = settings.cors_origins.split(",")
# Also allow common dev ports
for port in ["3000", "3001"]:
    origin = f"http://localhost:{port}"
    if origin not in _cors_origins:
        _cors_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


# --- Helpers ---


def get_or_create_session(session_id: str | None, user_id: str | None = None) -> str:
    sid = session_id or str(uuid4())
    if sid not in sessions:
        sessions[sid] = {"user_id": user_id}
    return sid


# --- Chat Endpoints ---


@app.post("/chat")
async def chat_stream(request: ChatRequest):
    """Chat with SSE streaming."""
    session_id = get_or_create_session(request.session_id, request.user_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            memory = await create_memory(session_id, request.user_id)
            agent = await create_agent(memory, tfl_client=tfl_client)

            async for event in run_agent_stream(agent, request.message, memory):
                yield event

            yield {"event": "done", "data": json.dumps({"session_id": session_id})}
        except Exception as e:
            logger.exception("Error in chat stream")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/chat/sync", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """Non-streaming chat endpoint."""
    session_id = get_or_create_session(request.session_id, request.user_id)

    try:
        memory = await create_memory(session_id, request.user_id)
        agent = await create_agent(memory, tfl_client=tfl_client)

        full_response = ""
        async for event in run_agent_stream(agent, request.message, memory):
            if event.get("event") == "token":
                data = json.loads(event["data"])
                full_response += data.get("content", "")

        return ChatResponse(response=full_response, session_id=session_id)
    except Exception as e:
        logger.exception("Error in sync chat")
        raise HTTPException(status_code=500, detail=str(e))


# --- Memory Endpoints ---


@app.get("/memory/context")
async def get_memory_context(
    session_id: str = Query(...),
    query: str = Query(""),
):
    """Get memory context for visualization."""
    client = get_memory_client()
    try:
        conversation = await client.short_term.get_conversation(session_id, limit=20)
        short_term = [
            {
                "id": str(m.id),
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "content": m.content[:200] + "..." if len(m.content) > 200 else m.content,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
            }
            for m in conversation.messages
        ]

        entities = await client.long_term.search_entities(query=query or "all", limit=20)
        preferences = await client.long_term.search_preferences(query=query or "all", limit=10)
        long_term = {
            "entities": [
                {
                    "id": str(e.id),
                    "name": e.display_name,
                    "type": e.type.value if hasattr(e.type, "value") else str(e.type),
                    "description": e.description,
                }
                for e in entities
            ],
            "preferences": [
                {
                    "id": str(p.id),
                    "category": p.category,
                    "preference": p.preference,
                    "context": p.context,
                }
                for p in preferences
            ],
        }

        traces = []
        if query:
            trace_results = await client.reasoning.get_similar_traces(task=query, limit=5)
            traces = [
                {
                    "id": str(t.id),
                    "task": t.task[:100],
                    "outcome": t.outcome,
                    "steps": len(t.steps) if t.steps else 0,
                }
                for t in trace_results
            ]

        return {"short_term": short_term, "long_term": long_term, "reasoning": traces}
    except Exception as e:
        logger.exception("Error getting memory context")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/graph")
async def get_memory_graph(
    session_id: str = Query(...),
):
    """Get memory graph for NVL visualization."""
    client = get_memory_client()
    try:
        query = """
        MATCH (m:Message {session_id: $session_id})-[:MENTIONS]->(e:Entity)
        WITH e, count(m) AS mentions
        ORDER BY mentions DESC LIMIT 20
        OPTIONAL MATCH (e)-[r]-(related:Entity)
        WITH collect(DISTINCT e) + collect(DISTINCT related) AS allNodes,
             collect(DISTINCT r) AS allRels
        RETURN [n IN allNodes WHERE n IS NOT NULL | {
            id: elementId(n),
            label: coalesce(n.name, 'Unknown'),
            type: labels(n)[0],
            properties: properties(n)
        }] AS nodes,
        [r IN allRels WHERE r IS NOT NULL | {
            id: elementId(r),
            source: elementId(startNode(r)),
            target: elementId(endNode(r)),
            type: type(r)
        }] AS relationships
        """
        result = await client.graph.execute_read(query, {"session_id": session_id})
        if not result:
            return {"nodes": [], "relationships": []}
        record = result[0]
        return {
            "nodes": record.get("nodes", []),
            "relationships": record.get("relationships", []),
        }
    except Exception as e:
        logger.exception("Error getting memory graph")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/preferences")
async def get_preferences(
    session_id: str = Query(...),
):
    """Get learned user preferences."""
    client = get_memory_client()
    try:
        preferences = await client.long_term.search_preferences(query="all", limit=50)
        return {
            "preferences": [
                {
                    "id": str(p.id),
                    "category": p.category,
                    "preference": p.preference,
                    "context": p.context,
                }
                for p in preferences
            ]
        }
    except Exception as e:
        logger.exception("Error getting preferences")
        raise HTTPException(status_code=500, detail=str(e))


# --- Transport Data Endpoints ---


@app.get("/stations")
async def get_stations(
    limit: int = Query(500),
):
    """Get all stations with coordinates for map rendering."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            MATCH (s:Station)
            OPTIONAL MATCH (s)-[:ON_LINE]->(l:Line)
            WITH s, collect({lineId: l.lineId, name: l.name, color: l.color}) AS lines
            RETURN s.naptanId AS naptanId, s.name AS name,
                   s.lat AS lat, s.lon AS lon, s.zone AS zone,
                   s.modes AS modes, lines
            LIMIT $limit
            """,
            {"limit": limit},
        )
        return {"stations": [dict(r) for r in result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stations/nearby")
async def get_nearby_stations(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(1000),
    limit: int = Query(10),
):
    """Find stations near a coordinate."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            WITH point({latitude: $lat, longitude: $lon}) AS location
            MATCH (s:Station)
            WHERE point.distance(s.location, location) < $radius
            WITH s, round(point.distance(s.location, location)) AS distance
            ORDER BY distance LIMIT $limit
            RETURN s.naptanId AS naptanId, s.name AS name,
                   s.lat AS lat, s.lon AS lon, s.zone AS zone, distance
            """,
            {"lat": lat, "lon": lon, "radius": radius, "limit": limit},
        )
        return {"stations": [dict(r) for r in result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stations/{naptan_id}")
async def get_station(naptan_id: str):
    """Get station details."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            MATCH (s:Station {naptanId: $id})
            OPTIONAL MATCH (s)-[:ON_LINE]->(l:Line)
            WITH s, collect({lineId: l.lineId, name: l.name, color: l.color}) AS lines
            OPTIONAL MATCH (b:BikePoint)-[r:NEAR_STATION]->(s)
            WITH s, lines, collect({name: b.name, distance: r.distance,
                                    nbBikes: b.nbBikes, nbDocks: b.nbDocks,
                                    lat: b.lat, lon: b.lon}) AS bikePoints
            OPTIONAL MATCH (s)-[:INTERCHANGE_WITH]-(other:Station)
            WITH s, lines, bikePoints, collect(other.name) AS interchanges
            RETURN s.naptanId AS naptanId, s.name AS name,
                   s.lat AS lat, s.lon AS lon, s.zone AS zone,
                   lines, bikePoints, interchanges
            """,
            {"id": naptan_id},
        )
        if not result:
            raise HTTPException(status_code=404, detail="Station not found")
        return dict(result[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/lines")
async def get_lines():
    """Get all lines with colors."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            MATCH (l:Line)
            OPTIONAL MATCH (s:Station)-[:ON_LINE]->(l)
            WITH l, count(s) AS stationCount
            RETURN l.lineId AS lineId, l.name AS name,
                   l.modeName AS modeName, l.color AS color,
                   stationCount
            ORDER BY l.name
            """,
            {},
        )
        return {"lines": [dict(r) for r in result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/lines/{line_id}/stations")
async def get_line_stations(line_id: str):
    """Get stations on a line in order."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            MATCH (s:Station)-[r:ON_LINE]->(l:Line {lineId: $lineId})
            RETURN s.naptanId AS naptanId, s.name AS name,
                   s.lat AS lat, s.lon AS lon, s.zone AS zone,
                   r.sequence AS sequence,
                   l.name AS lineName, l.color AS lineColor
            ORDER BY r.sequence
            """,
            {"lineId": line_id},
        )
        return {"stations": [dict(r) for r in result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/lines/{line_id}/graph")
async def get_line_graph(line_id: str):
    """Get the full subgraph for a line: stations, zones, bike points, and relationships."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            MATCH (s:Station)-[r:ON_LINE]->(l:Line {lineId: $lineId})
            WITH s, r.sequence AS seq, l
            ORDER BY seq
            OPTIONAL MATCH (s)-[:IN_ZONE]->(z:Zone)
            OPTIONAL MATCH (b:BikePoint)-[:NEAR_STATION]->(s)
            RETURN s.naptanId AS naptanId, s.name AS name,
                   s.lat AS lat, s.lon AS lon, s.zone AS zone,
                   seq AS sequence,
                   l.name AS lineName, l.color AS lineColor,
                   collect(DISTINCT z.number) AS zones,
                   collect(DISTINCT {id: b.id, name: b.name, lat: b.lat, lon: b.lon,
                                     nbBikes: b.nbBikes, nbDocks: b.nbDocks}) AS bikePoints
            ORDER BY sequence
            """,
            {"lineId": line_id},
        )

        nodes = []
        relationships = []
        seen_zone_ids = set()
        seen_bp_ids = set()
        station_ids = []

        for row in result:
            r = dict(row)
            station_id = r["naptanId"]
            station_ids.append(station_id)

            # Station node
            nodes.append({
                "id": station_id,
                "label": r["name"],
                "type": "Station",
                "properties": {
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "zone": r["zone"],
                    "sequence": r["sequence"],
                    "line": r["lineName"],
                    "lineColor": r["lineColor"],
                },
            })

            # Zone nodes and IN_ZONE relationships
            for zone_num in r["zones"]:
                if zone_num is None:
                    continue
                zone_id = f"zone-{zone_num}"
                if zone_id not in seen_zone_ids:
                    seen_zone_ids.add(zone_id)
                    nodes.append({
                        "id": zone_id,
                        "label": f"Zone {zone_num}",
                        "type": "Zone",
                        "properties": {"number": zone_num},
                    })
                relationships.append({
                    "id": f"inzone-{station_id}-{zone_num}",
                    "source": station_id,
                    "target": zone_id,
                    "type": "IN_ZONE",
                })

            # BikePoint nodes and NEAR_STATION relationships
            for bp in r["bikePoints"]:
                if bp.get("id") is None:
                    continue
                bp_id = bp["id"]
                if bp_id not in seen_bp_ids:
                    seen_bp_ids.add(bp_id)
                    nodes.append({
                        "id": bp_id,
                        "label": (bp.get("name") or "Bike Point").replace(
                            ", London", ""
                        ),
                        "type": "BikePoint",
                        "properties": {
                            "lat": bp["lat"],
                            "lon": bp["lon"],
                            "nbBikes": bp["nbBikes"],
                            "nbDocks": bp["nbDocks"],
                        },
                    })
                relationships.append({
                    "id": f"near-{bp_id}-{station_id}",
                    "source": bp_id,
                    "target": station_id,
                    "type": "NEAR_STATION",
                })

        # NEXT_STOP relationships between consecutive stations
        for i in range(len(station_ids) - 1):
            relationships.append({
                "id": f"next-{i}",
                "source": station_ids[i],
                "target": station_ids[i + 1],
                "type": "NEXT_STOP",
            })

        return {"nodes": nodes, "relationships": relationships}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/bikepoints/nearby")
async def get_nearby_bikepoints(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(500),
    limit: int = Query(10),
):
    """Find bike points near a coordinate."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            WITH point({latitude: $lat, longitude: $lon}) AS location
            MATCH (b:BikePoint)
            WHERE point.distance(b.location, location) < $radius
            WITH b, round(point.distance(b.location, location)) AS distance
            ORDER BY distance LIMIT $limit
            RETURN b.id AS id, b.name AS name,
                   b.lat AS lat, b.lon AS lon,
                   b.nbDocks AS nbDocks, b.nbBikes AS nbBikes,
                   b.nbEmptyDocks AS nbEmptyDocks, distance
            """,
            {"lat": lat, "lon": lon, "radius": radius, "limit": limit},
        )
        return {"bikepoints": [dict(r) for r in result]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/neighborhood/{node_id}")
async def get_graph_neighborhood(node_id: str):
    """Get graph neighborhood of a node for NVL expansion."""
    client = get_memory_client()
    try:
        result = await client.graph.execute_read(
            """
            MATCH (n)
            WHERE elementId(n) = $nodeId OR n.naptanId = $nodeId OR n.lineId = $nodeId
            WITH n LIMIT 1
            OPTIONAL MATCH (n)-[r]-(neighbor)
            WITH n, collect(DISTINCT {
                id: coalesce(neighbor.naptanId, neighbor.lineId, neighbor.id, elementId(neighbor)),
                label: coalesce(neighbor.name, 'Unknown'),
                type: labels(neighbor)[0],
                properties: {lat: neighbor.lat, lon: neighbor.lon, color: neighbor.color, zone: neighbor.zone}
            }) AS neighbors,
            collect(DISTINCT {
                source: coalesce(n.naptanId, n.lineId, n.id, elementId(n)),
                target: coalesce(neighbor.naptanId, neighbor.lineId, neighbor.id, elementId(neighbor)),
                type: type(r)
            }) AS relationships
            RETURN {
                id: coalesce(n.naptanId, n.lineId, n.id, elementId(n)),
                label: coalesce(n.name, 'Unknown'),
                type: labels(n)[0],
                properties: {lat: n.lat, lon: n.lon, color: n.color, zone: n.zone}
            } AS center,
            neighbors, relationships
            """,
            {"nodeId": node_id},
        )
        if not result:
            raise HTTPException(status_code=404, detail="Node not found")
        record = result[0]
        return {
            "center": record["center"],
            "nodes": [record["center"]] + record["neighbors"],
            "relationships": record["relationships"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/disruptions")
async def get_disruptions():
    """Get current disruptions."""
    if tfl_client is None:
        raise HTTPException(status_code=503, detail="TfL client not available")
    disruptions = await tfl_client.get_disruptions()
    return {"disruptions": disruptions}


# --- Health Check ---


@app.get("/health")
async def health_check():
    """Health check."""
    try:
        client = get_memory_client()
        db_connected = client is not None and client.is_connected
    except Exception:
        db_connected = False

    return {
        "status": "healthy" if db_connected else "degraded",
        "database": "connected" if db_connected else "disconnected",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
