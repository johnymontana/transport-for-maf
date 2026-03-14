"""Integration tests for Neo4j graph operations.

These tests require a running Neo4j instance (via env vars or testcontainers).
They verify schema creation, data loading, and spatial queries work correctly.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestSchemaCreation:
    """Test that constraints and indexes can be created."""

    @pytest.mark.asyncio
    async def test_create_station_constraint(self, neo4j_driver):
        async with neo4j_driver.session() as session:
            await session.run(
                "CREATE CONSTRAINT station_naptan IF NOT EXISTS "
                "FOR (s:Station) REQUIRE s.naptanId IS UNIQUE"
            )
            result = await session.run("SHOW CONSTRAINTS")
            constraints = [r async for r in result]
            names = [c["name"] for c in constraints]
            assert any("station" in n.lower() for n in names)

    @pytest.mark.asyncio
    async def test_create_spatial_index(self, neo4j_driver):
        async with neo4j_driver.session() as session:
            await session.run(
                "CREATE POINT INDEX station_location IF NOT EXISTS "
                "FOR (s:Station) ON (s.location)"
            )
            result = await session.run("SHOW INDEXES")
            indexes = [r async for r in result]
            point_indexes = [i for i in indexes if i.get("type") == "POINT"]
            assert len(point_indexes) >= 1


@pytest.mark.integration
class TestStationLoading:
    """Test loading station data into Neo4j."""

    @pytest.mark.asyncio
    async def test_create_station_with_point(self, neo4j_driver):
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (s:Station {
                    naptanId: '940GZZLUWLO',
                    name: 'Waterloo Underground Station',
                    lat: 51.5031,
                    lon: -0.1132,
                    location: point({latitude: 51.5031, longitude: -0.1132}),
                    zone: '1',
                    modes: ['tube']
                })
                """
            )
            result = await session.run(
                "MATCH (s:Station {naptanId: '940GZZLUWLO'}) RETURN s"
            )
            records = [r async for r in result]
            assert len(records) == 1
            node = records[0]["s"]
            assert node["name"] == "Waterloo Underground Station"
            assert node["lat"] == pytest.approx(51.5031)

    @pytest.mark.asyncio
    async def test_spatial_distance_query(self, neo4j_driver):
        """Test point.distance() spatial query."""
        async with neo4j_driver.session() as session:
            # Create two stations
            await session.run(
                """
                CREATE (s1:Station {
                    naptanId: 'S1', name: 'Station A',
                    lat: 51.5031, lon: -0.1132,
                    location: point({latitude: 51.5031, longitude: -0.1132})
                })
                CREATE (s2:Station {
                    naptanId: 'S2', name: 'Station B',
                    lat: 51.5074, lon: -0.1278,
                    location: point({latitude: 51.5074, longitude: -0.1278})
                })
                """
            )
            # Find stations within 2km of a point
            result = await session.run(
                """
                WITH point({latitude: 51.505, longitude: -0.12}) AS ref
                MATCH (s:Station)
                WHERE point.distance(s.location, ref) < 2000
                RETURN s.name AS name, round(point.distance(s.location, ref)) AS distance
                ORDER BY distance
                """
            )
            records = [r async for r in result]
            assert len(records) >= 1
            # All returned should be within 2000m
            for r in records:
                assert r["distance"] < 2000


@pytest.mark.integration
class TestRelationships:
    """Test creating relationships between transport entities."""

    @pytest.mark.asyncio
    async def test_on_line_relationship(self, neo4j_driver):
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (s:Station {naptanId: 'S_OL1', name: 'Test Station'})
                CREATE (l:Line {lineId: 'northern', name: 'Northern', color: '#000000'})
                CREATE (s)-[:ON_LINE {sequence: 1}]->(l)
                """
            )
            result = await session.run(
                """
                MATCH (s:Station {naptanId: 'S_OL1'})-[r:ON_LINE]->(l:Line)
                RETURN l.name AS lineName, r.sequence AS seq
                """
            )
            records = [r async for r in result]
            assert len(records) == 1
            assert records[0]["lineName"] == "Northern"
            assert records[0]["seq"] == 1

    @pytest.mark.asyncio
    async def test_next_stop_chain(self, neo4j_driver):
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (s1:Station {naptanId: 'NS1', name: 'First'})
                CREATE (s2:Station {naptanId: 'NS2', name: 'Second'})
                CREATE (s3:Station {naptanId: 'NS3', name: 'Third'})
                CREATE (s1)-[:NEXT_STOP {lineId: 'northern'}]->(s2)
                CREATE (s2)-[:NEXT_STOP {lineId: 'northern'}]->(s3)
                """
            )
            # Find path from First to Third
            result = await session.run(
                """
                MATCH path = shortestPath(
                    (start:Station {naptanId: 'NS1'})-[:NEXT_STOP*]-(end:Station {naptanId: 'NS3'})
                )
                RETURN [n IN nodes(path) | n.name] AS stops
                """
            )
            records = [r async for r in result]
            assert len(records) == 1
            assert records[0]["stops"] == ["First", "Second", "Third"]

    @pytest.mark.asyncio
    async def test_interchange_relationship(self, neo4j_driver):
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (s1:Station {naptanId: 'IX1', name: 'King Cross Tube',
                    location: point({latitude: 51.5308, longitude: -0.1238})})
                CREATE (s2:Station {naptanId: 'IX2', name: 'King Cross Rail',
                    location: point({latitude: 51.5310, longitude: -0.1240})})
                CREATE (s1)-[:INTERCHANGE_WITH]->(s2)
                CREATE (s2)-[:INTERCHANGE_WITH]->(s1)
                """
            )
            result = await session.run(
                """
                MATCH (s:Station {naptanId: 'IX1'})-[:INTERCHANGE_WITH]->(other)
                RETURN other.name AS name
                """
            )
            records = [r async for r in result]
            assert len(records) == 1
            assert records[0]["name"] == "King Cross Rail"


@pytest.mark.integration
class TestBikePoints:
    """Test bike point spatial queries."""

    @pytest.mark.asyncio
    async def test_bikepoint_near_station(self, neo4j_driver):
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (s:Station {
                    naptanId: 'BP_S1', name: 'Near Station',
                    location: point({latitude: 51.503, longitude: -0.113})
                })
                CREATE (b:BikePoint {
                    id: 'BikePoints_99', name: 'Test Dock',
                    lat: 51.504, lon: -0.114,
                    location: point({latitude: 51.504, longitude: -0.114}),
                    nbDocks: 20, nbBikes: 10
                })
                CREATE (b)-[:NEAR_STATION {distance: 150}]->(s)
                """
            )
            result = await session.run(
                """
                MATCH (b:BikePoint)-[r:NEAR_STATION]->(s:Station {naptanId: 'BP_S1'})
                RETURN b.name AS name, b.nbBikes AS bikes, r.distance AS distance
                """
            )
            records = [r async for r in result]
            assert len(records) == 1
            assert records[0]["name"] == "Test Dock"
            assert records[0]["bikes"] == 10
