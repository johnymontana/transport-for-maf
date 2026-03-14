// Constraints
CREATE CONSTRAINT station_naptan_id IF NOT EXISTS
FOR (s:Station) REQUIRE s.naptanId IS UNIQUE;

CREATE CONSTRAINT line_id IF NOT EXISTS
FOR (l:Line) REQUIRE l.lineId IS UNIQUE;

CREATE CONSTRAINT bikepoint_id IF NOT EXISTS
FOR (b:BikePoint) REQUIRE b.id IS UNIQUE;

CREATE CONSTRAINT zone_number IF NOT EXISTS
FOR (z:Zone) REQUIRE z.number IS UNIQUE;

// Spatial indexes
CREATE POINT INDEX station_location IF NOT EXISTS
FOR (s:Station) ON (s.location);

CREATE POINT INDEX bikepoint_location IF NOT EXISTS
FOR (b:BikePoint) ON (b.location);

// Text index for fuzzy station search
CREATE TEXT INDEX station_name IF NOT EXISTS
FOR (s:Station) ON (s.name);
