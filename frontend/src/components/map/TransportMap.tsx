"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Map, {
  Marker,
  NavigationControl,
  Source,
  Layer,
  type MapRef,
  type ViewStateChangeEvent,
} from "react-map-gl";
import { Box, Text } from "@chakra-ui/react";
import { useAppStore } from "@/store/useAppStore";
import type { Station } from "@/lib/types";
import "mapbox-gl/dist/mapbox-gl.css";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

const LONDON_CENTER = {
  latitude: 51.505,
  longitude: -0.09,
  zoom: 12,
};

function shortName(name: string) {
  return name.replace(/ Underground Station$/, "").replace(/ Station$/, "");
}

export function TransportMap() {
  const mapRef = useRef<MapRef>(null);
  const {
    mapCenter,
    mapZoom,
    mapMarkers,
    routeCoordinates,
    selectedStation,
    setSelectedStation,
    memoryLocations,
    allStations,
    loadStations,
  } = useAppStore();

  const [viewState, setViewState] = useState({
    latitude: LONDON_CENTER.latitude,
    longitude: LONDON_CENTER.longitude,
    zoom: LONDON_CENTER.zoom,
  });

  // Load all stations on mount (cached in store)
  useEffect(() => {
    loadStations();
  }, [loadStations]);

  // Fly to when mapCenter changes from store
  useEffect(() => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [mapCenter.lon, mapCenter.lat],
        zoom: mapZoom,
        duration: 1500,
      });
    }
  }, [mapCenter, mapZoom]);

  // When map loads (or re-mounts), fly to current store position if not default
  const handleMapLoad = useCallback(() => {
    const { mapCenter: center, mapZoom: zoom } = useAppStore.getState();
    if (
      center.lat !== LONDON_CENTER.latitude ||
      center.lon !== LONDON_CENTER.longitude
    ) {
      mapRef.current?.flyTo({
        center: [center.lon, center.lat],
        zoom,
        duration: 800,
      });
    }
  }, []);

  const handleMoveEnd = useCallback((e: ViewStateChangeEvent) => {
    setViewState(e.viewState);
  }, []);

  const handleStationClick = useCallback(
    (station: Station) => {
      setSelectedStation(station);
    },
    [setSelectedStation]
  );

  // GeoJSON for route line
  const routeGeoJSON = routeCoordinates
    ? {
        type: "Feature" as const,
        properties: {},
        geometry: {
          type: "LineString" as const,
          coordinates: routeCoordinates,
        },
      }
    : null;

  if (!MAPBOX_TOKEN) {
    return (
      <Box
        w="100%"
        h="100%"
        display="flex"
        alignItems="center"
        justifyContent="center"
        bg="gray.100"
      >
        <Text color="gray.500">
          Set NEXT_PUBLIC_MAPBOX_TOKEN in .env to enable the map
        </Text>
      </Box>
    );
  }

  return (
    <Map
      ref={mapRef}
      initialViewState={viewState}
      onMoveEnd={handleMoveEnd}
      onLoad={handleMapLoad}
      mapboxAccessToken={MAPBOX_TOKEN}
      mapStyle="mapbox://styles/mapbox/light-v11"
      style={{ width: "100%", height: "100%" }}
    >
      <NavigationControl position="top-right" />

      {/* All stations as dots when zoomed out */}
      {viewState.zoom < 13 &&
        allStations.map((station) => (
          <Marker
            key={station.naptanId}
            latitude={station.lat}
            longitude={station.lon}
            anchor="center"
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              handleStationClick(station);
            }}
          >
            <div
              aria-label={station.name}
              title={station.name}
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor:
                  selectedStation?.naptanId === station.naptanId
                    ? "#E32017"
                    : "#DA7194",
                border: "1px solid white",
                cursor: "pointer",
              }}
            />
          </Marker>
        ))}

      {/* All stations with labels when zoomed in */}
      {viewState.zoom >= 13 &&
        allStations
          .filter(
            (s) =>
              Math.abs(s.lat - viewState.latitude) < 0.03 &&
              Math.abs(s.lon - viewState.longitude) < 0.05
          )
          .map((station) => (
            <Marker
              key={station.naptanId}
              latitude={station.lat}
              longitude={station.lon}
              anchor="center"
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                handleStationClick(station);
              }}
            >
              <div
                aria-label={station.name}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  cursor: "pointer",
                }}
              >
                <div
                  style={{
                    width:
                      selectedStation?.naptanId === station.naptanId ? 18 : 14,
                    height:
                      selectedStation?.naptanId === station.naptanId ? 18 : 14,
                    borderRadius: "50%",
                    backgroundColor:
                      selectedStation?.naptanId === station.naptanId
                        ? "#E32017"
                        : "#DA7194",
                    border: "2px solid white",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                  }}
                />
                {viewState.zoom >= 14 && (
                  <Text
                    fontSize="9px"
                    fontWeight="bold"
                    color="gray.700"
                    mt={0.5}
                    textAlign="center"
                    maxW="80px"
                    lineClamp={1}
                    bg="rgba(255,255,255,0.8)"
                    px={0.5}
                    borderRadius="sm"
                    title={station.name}
                  >
                    {shortName(station.name)}
                  </Text>
                )}
              </div>
            </Marker>
          ))}

      {/* Dynamic markers from agent tool results */}
      {mapMarkers.map((marker, i) => (
        <Marker
          key={`marker-${i}`}
          latitude={marker.lat}
          longitude={marker.lon}
          anchor="center"
        >
          <div
            aria-label={marker.name}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
            }}
          >
            <div
              style={{
                width: marker.type === "bikepoint" ? 10 : 16,
                height: marker.type === "bikepoint" ? 10 : 16,
                borderRadius: "50%",
                backgroundColor:
                  marker.type === "bikepoint"
                    ? "#2F9E44"
                    : marker.type === "route_stop"
                      ? "#003688"
                      : "#E32017",
                border: "2px solid white",
                boxShadow: "0 1px 4px rgba(0,0,0,0.4)",
              }}
            />
            <Text
              fontSize="8px"
              fontWeight="bold"
              color="gray.700"
              mt={0.5}
              bg="rgba(255,255,255,0.9)"
              px={1}
              borderRadius="sm"
              maxW="100px"
              textAlign="center"
              lineClamp={1}
              title={marker.name}
            >
              {shortName(marker.name)}
            </Text>
          </div>
        </Marker>
      ))}

      {/* Memory location markers (geocoded entities from conversations) */}
      {memoryLocations.map((loc, i) => (
        <Marker
          key={`memory-${i}`}
          latitude={loc.lat}
          longitude={loc.lon}
          anchor="center"
        >
          <div
            aria-label={loc.name}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
            }}
          >
            <div
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                backgroundColor: "#6366F1",
                border: "2px solid white",
                boxShadow: "0 1px 4px rgba(0,0,0,0.4)",
              }}
            />
            <Text
              fontSize="8px"
              fontWeight="bold"
              color="purple.700"
              mt={0.5}
              bg="rgba(255,255,255,0.9)"
              px={1}
              borderRadius="sm"
              maxW="100px"
              textAlign="center"
              lineClamp={1}
              title={loc.name}
            >
              {loc.name}
            </Text>
          </div>
        </Marker>
      ))}

      {/* Route line */}
      {routeGeoJSON && (
        <Source type="geojson" data={routeGeoJSON}>
          <Layer
            id="route-line"
            type="line"
            paint={{
              "line-color": "#003688",
              "line-width": 4,
              "line-opacity": 0.8,
            }}
          />
        </Source>
      )}
    </Map>
  );
}
