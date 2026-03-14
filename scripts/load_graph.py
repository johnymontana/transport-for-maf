"""Load TfL data into Neo4j.

Reads JSON files from data/ directory and creates the transport graph
with spatial indexes and geospatial relationships.

Usage:
    python load_graph.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


async def run_schema(driver) -> None:
    """Create constraints and indexes."""
    print("Creating schema...")
    schema_file = Path(__file__).parent.parent / "cypher" / "schema.cypher"
    statements = schema_file.read_text()

    async with driver.session() as session:
        for stmt in statements.split(";"):
            stmt = stmt.strip()
            # Skip empty and comment-only lines
            if not stmt or all(
                line.strip().startswith("//") or not line.strip()
                for line in stmt.split("\n")
            ):
                continue
            # Remove comments from the statement
            clean_lines = [
                line for line in stmt.split("\n") if not line.strip().startswith("//")
            ]
            clean_stmt = "\n".join(clean_lines).strip()
            if clean_stmt:
                try:
                    await session.run(clean_stmt)
                    print(f"  OK: {clean_stmt[:60]}...")
                except Exception as e:
                    print(f"  Warning: {e}")

    print("  Schema created.")


async def load_stations(driver) -> None:
    """Load stations with point() coordinates."""
    stations_file = DATA_DIR / "stations.json"
    if not stations_file.exists():
        print("  Skipping stations: data/stations.json not found")
        return

    stations = json.loads(stations_file.read_text())
    print(f"Loading {len(stations)} stations...")

    async with driver.session() as session:
        # Batch load stations
        await session.run(
            """
            UNWIND $stations AS s
            MERGE (station:Station {naptanId: s.naptanId})
            SET station.name = s.commonName,
                station.location = point({latitude: s.lat, longitude: s.lon}),
                station.lat = s.lat,
                station.lon = s.lon,
                station.modes = s.modes,
                station.zone = s.zone
            """,
            stations=stations,
        )

        # Create Zone nodes and IN_ZONE relationships
        await session.run(
            """
            MATCH (s:Station)
            WHERE s.zone IS NOT NULL
            WITH s, s.zone AS zoneStr
            MERGE (z:Zone {number: zoneStr})
            MERGE (s)-[:IN_ZONE]->(z)
            """
        )

    async with driver.session() as session:
        result = await session.run("MATCH (s:Station) RETURN count(s) AS count")
        record = await result.single()
        print(f"  Loaded {record['count']} stations.")


async def load_lines(driver) -> None:
    """Load lines and ON_LINE relationships."""
    lines_file = DATA_DIR / "lines.json"
    if not lines_file.exists():
        print("  Skipping lines: data/lines.json not found")
        return

    lines = json.loads(lines_file.read_text())
    print(f"Loading {len(lines)} lines...")

    async with driver.session() as session:
        # Load line nodes
        await session.run(
            """
            UNWIND $lines AS l
            MERGE (line:Line {lineId: l.id})
            SET line.name = l.name,
                line.modeName = l.modeName,
                line.color = l.color
            """,
            lines=lines,
        )

    # Create ON_LINE relationships from station line data (batched)
    stations_file = DATA_DIR / "stations.json"
    if stations_file.exists():
        stations = json.loads(stations_file.read_text())
        # Build flat list of {naptanId, lineId} pairs
        pairs = []
        for station in stations:
            for line_ref in station.get("lines", []):
                pairs.append({
                    "naptanId": station["naptanId"],
                    "lineId": line_ref["id"],
                })
        async with driver.session() as session:
            await session.run(
                """
                UNWIND $pairs AS p
                MATCH (s:Station {naptanId: p.naptanId})
                MATCH (l:Line {lineId: p.lineId})
                MERGE (s)-[:ON_LINE]->(l)
                """,
                pairs=pairs,
            )

    print("  Lines loaded.")


async def load_routes(driver) -> None:
    """Load route sequences as NEXT_STOP relationships."""
    routes_dir = DATA_DIR / "routes"
    if not routes_dir.exists():
        print("  Skipping routes: data/routes/ not found")
        return

    route_files = list(routes_dir.glob("*.json"))
    print(f"Loading routes from {len(route_files)} line files...")

    # Collect all NEXT_STOP pairs and ON_LINE pairs across all lines
    next_stop_pairs = []
    on_line_pairs = []

    for route_file in route_files:
        route_data = json.loads(route_file.read_text())
        line_id = route_data["lineId"]
        line_name = route_data["lineName"]

        for branch in route_data.get("sequences", []):
            stops = branch.get("stops", branch) if isinstance(branch, dict) else branch

            for i in range(len(stops) - 1):
                next_stop_pairs.append({
                    "fromId": stops[i]["naptanId"],
                    "toId": stops[i + 1]["naptanId"],
                    "lineId": line_id,
                    "lineName": line_name,
                    "seq": i,
                })

            for stop in stops:
                on_line_pairs.append({
                    "naptanId": stop["naptanId"],
                    "lineId": line_id,
                    "seq": stop["sequence"],
                })

    print(f"  Batch loading {len(next_stop_pairs)} NEXT_STOP and {len(on_line_pairs)} ON_LINE pairs...")

    async with driver.session() as session:
        # Batch NEXT_STOP in chunks to avoid query size limits
        chunk_size = 500
        for i in range(0, len(next_stop_pairs), chunk_size):
            chunk = next_stop_pairs[i : i + chunk_size]
            await session.run(
                """
                UNWIND $pairs AS p
                MATCH (a:Station {naptanId: p.fromId})
                MATCH (b:Station {naptanId: p.toId})
                MERGE (a)-[r:NEXT_STOP {lineId: p.lineId}]->(b)
                SET r.lineName = p.lineName, r.sequence = p.seq
                """,
                pairs=chunk,
            )

        # Batch ON_LINE with sequence
        for i in range(0, len(on_line_pairs), chunk_size):
            chunk = on_line_pairs[i : i + chunk_size]
            await session.run(
                """
                UNWIND $pairs AS p
                MATCH (s:Station {naptanId: p.naptanId})
                MATCH (l:Line {lineId: p.lineId})
                MERGE (s)-[r:ON_LINE]->(l)
                ON CREATE SET r.sequence = p.seq
                """,
                pairs=chunk,
            )

    async with driver.session() as session:
        result = await session.run(
            "MATCH ()-[r:NEXT_STOP]->() RETURN count(r) AS count"
        )
        record = await result.single()
        print(f"  Created {record['count']} NEXT_STOP relationships.")


async def load_bikepoints(driver) -> None:
    """Load bike points with spatial coordinates."""
    bikepoints_file = DATA_DIR / "bikepoints.json"
    if not bikepoints_file.exists():
        print("  Skipping bike points: data/bikepoints.json not found")
        return

    bikepoints = json.loads(bikepoints_file.read_text())
    print(f"Loading {len(bikepoints)} bike points...")

    async with driver.session() as session:
        # Batch load in chunks of 500
        chunk_size = 500
        for i in range(0, len(bikepoints), chunk_size):
            chunk = bikepoints[i : i + chunk_size]
            await session.run(
                """
                UNWIND $bikepoints AS bp
                MERGE (b:BikePoint {id: bp.id})
                SET b.name = bp.commonName,
                    b.location = point({latitude: bp.lat, longitude: bp.lon}),
                    b.lat = bp.lat,
                    b.lon = bp.lon,
                    b.nbDocks = bp.nbDocks,
                    b.nbBikes = bp.nbBikes,
                    b.nbEmptyDocks = bp.nbEmptyDocks
                """,
                bikepoints=chunk,
            )

    print(f"  Loaded {len(bikepoints)} bike points.")


async def create_spatial_relationships(driver) -> None:
    """Create NEAR_STATION and INTERCHANGE_WITH spatial relationships."""
    print("Creating spatial relationships...")

    async with driver.session() as session:
        # NEAR_STATION: bike points within 500m of stations
        print("  Creating NEAR_STATION relationships (bike points within 500m)...")
        result = await session.run(
            """
            MATCH (b:BikePoint), (s:Station)
            WHERE point.distance(b.location, s.location) < 500
            MERGE (b)-[r:NEAR_STATION]->(s)
            SET r.distance = round(point.distance(b.location, s.location))
            RETURN count(r) AS count
            """
        )
        record = await result.single()
        print(f"    Created {record['count']} NEAR_STATION relationships.")

        # INTERCHANGE_WITH: stations within 100m of each other (different stations)
        print("  Creating INTERCHANGE_WITH relationships (stations within 100m)...")
        result = await session.run(
            """
            MATCH (a:Station), (b:Station)
            WHERE a <> b
              AND a.naptanId < b.naptanId
              AND point.distance(a.location, b.location) < 100
            MERGE (a)-[:INTERCHANGE_WITH]-(b)
            RETURN count(*) AS count
            """
        )
        record = await result.single()
        print(f"    Created {record['count']} INTERCHANGE_WITH relationships.")


async def print_summary(driver) -> None:
    """Print a summary of loaded data."""
    print("\n--- Graph Summary ---")
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (s:Station) WITH count(s) AS stations
            MATCH (l:Line) WITH stations, count(l) AS lines
            MATCH (b:BikePoint) WITH stations, lines, count(b) AS bikepoints
            MATCH (z:Zone) WITH stations, lines, bikepoints, count(z) AS zones
            RETURN stations, lines, bikepoints, zones
            """
        )
        record = await result.single()
        print(f"  Stations:   {record['stations']}")
        print(f"  Lines:      {record['lines']}")
        print(f"  BikePoints: {record['bikepoints']}")
        print(f"  Zones:      {record['zones']}")

        result = await session.run(
            """
            MATCH ()-[r:NEXT_STOP]->() WITH count(r) AS nextStop
            MATCH ()-[r:ON_LINE]->() WITH nextStop, count(r) AS onLine
            MATCH ()-[r:NEAR_STATION]->() WITH nextStop, onLine, count(r) AS nearStation
            MATCH ()-[r:INTERCHANGE_WITH]-() WITH nextStop, onLine, nearStation, count(r) AS interchange
            MATCH ()-[r:IN_ZONE]->() WITH nextStop, onLine, nearStation, interchange, count(r) AS inZone
            RETURN nextStop, onLine, nearStation, interchange, inZone
            """
        )
        record = await result.single()
        print(f"  NEXT_STOP:       {record['nextStop']}")
        print(f"  ON_LINE:         {record['onLine']}")
        print(f"  NEAR_STATION:    {record['nearStation']}")
        print(f"  INTERCHANGE_WITH: {record['interchange']}")
        print(f"  IN_ZONE:         {record['inZone']}")


async def main() -> None:
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        await run_schema(driver)
        await load_stations(driver)
        await load_lines(driver)
        await load_routes(driver)
        await load_bikepoints(driver)
        await create_spatial_relationships(driver)
        await print_summary(driver)
    finally:
        await driver.close()

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
