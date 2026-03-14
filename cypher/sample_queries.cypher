// Nearest stations to a coordinate (e.g., Big Ben)
WITH point({latitude: 51.5007, longitude: -0.1246}) AS location
MATCH (s:Station)
WHERE point.distance(s.location, location) < 1000
RETURN s.name, round(point.distance(s.location, location)) AS distanceMeters
ORDER BY distanceMeters
LIMIT 10;

// Stations within a bounding box (central London)
MATCH (s:Station)
WHERE point.withinBBox(
  s.location,
  point({latitude: 51.49, longitude: -0.15}),
  point({latitude: 51.53, longitude: -0.08})
)
RETURN s.name, s.location;

// Shortest route between two stations
MATCH path = shortestPath(
  (start:Station {name: "King's Cross St. Pancras Underground Station"})
  -[:NEXT_STOP*]-
  (end:Station {name: "Brixton Underground Station"})
)
RETURN [n IN nodes(path) | n.name] AS route, length(path) AS stops;

// All stations on a line in order
MATCH (s:Station)-[r:ON_LINE]->(l:Line {name: "Northern"})
RETURN s.name, r.sequence
ORDER BY r.sequence;

// Bike points near a station with availability
MATCH (s:Station)
WHERE s.name CONTAINS "Waterloo"
MATCH (b:BikePoint)
WHERE point.distance(b.location, s.location) < 500
RETURN b.name, b.nbDocks,
       round(point.distance(b.location, s.location)) AS distanceMeters
ORDER BY distanceMeters;

// Interchange stations (connected to multiple lines)
MATCH (s:Station)-[:ON_LINE]->(l:Line)
WITH s, collect(l.name) AS lines, count(l) AS lineCount
WHERE lineCount > 1
RETURN s.name, lines, lineCount
ORDER BY lineCount DESC
LIMIT 20;

// Station count per zone
MATCH (s:Station)-[:IN_ZONE]->(z:Zone)
RETURN z.number AS zone, count(s) AS stationCount
ORDER BY z.number;
