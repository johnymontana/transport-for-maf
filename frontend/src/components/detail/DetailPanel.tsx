"use client";

import { useEffect, useState } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Badge,
  Heading,
  Card,
  Spinner,
} from "@chakra-ui/react";
import { useAppStore } from "@/store/useAppStore";
import { getStationDetails, getPreferences } from "@/lib/api";
import { TFL_LINE_COLORS } from "@/lib/graphStyles";

interface StationDetails {
  naptanId: string;
  name: string;
  lat: number;
  lon: number;
  zone: string | null;
  lines: Array<{ lineId: string; name: string; color: string }>;
  bikePoints: Array<{
    name: string;
    distance: number;
    nbBikes: number;
    nbDocks: number;
  }>;
  interchanges: string[];
}

export function DetailPanel() {
  const { selectedStation, selectedLine, sessionId } = useAppStore();
  const [stationDetails, setStationDetails] = useState<StationDetails | null>(
    null
  );
  const [preferences, setPreferences] = useState<
    Array<{ id: string; category: string; preference: string }>
  >([]);
  const [loading, setLoading] = useState(false);

  // Load station details when selected
  useEffect(() => {
    if (!selectedStation) {
      setStationDetails(null);
      return;
    }
    setLoading(true);
    getStationDetails(selectedStation.naptanId)
      .then((data) => setStationDetails(data as unknown as StationDetails))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedStation]);

  // Load preferences
  useEffect(() => {
    getPreferences(sessionId)
      .then((data) => setPreferences(data.preferences))
      .catch(() => setPreferences([]));
  }, [sessionId]);

  return (
    <Box h="100%" overflowY="auto" bg="gray.50" borderLeft="1px solid" borderColor="gray.200" p={4}>
      <VStack align="stretch" gap={4}>
        {/* Station details */}
        {loading && (
          <Box textAlign="center" py={8}>
            <Spinner />
          </Box>
        )}

        {stationDetails && !loading && (
          <Card.Root>
            <Card.Body p={4}>
              <Heading size="sm" mb={2}>
                {stationDetails.name
                  .replace(/ Underground Station$/, "")
                  .replace(/ Station$/, "")}
              </Heading>

              {stationDetails.zone && (
                <Badge colorPalette="orange" mb={2}>
                  Zone {stationDetails.zone}
                </Badge>
              )}

              {/* Lines */}
              {stationDetails.lines.length > 0 && (
                <Box mb={3}>
                  <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>
                    Lines
                  </Text>
                  <HStack gap={1} flexWrap="wrap">
                    {stationDetails.lines.map((line) => (
                      <Badge
                        key={line.lineId}
                        bg={
                          TFL_LINE_COLORS[line.lineId] ||
                          line.color ||
                          "gray.500"
                        }
                        color={
                          ["circle", "hammersmith-city", "waterloo-city"].includes(
                            line.lineId
                          )
                            ? "black"
                            : "white"
                        }
                        fontSize="xs"
                        px={2}
                      >
                        {line.name}
                      </Badge>
                    ))}
                  </HStack>
                </Box>
              )}

              {/* Interchanges */}
              {stationDetails.interchanges.length > 0 && (
                <Box mb={3}>
                  <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>
                    Interchanges
                  </Text>
                  {stationDetails.interchanges.map((name, i) => (
                    <Text key={i} fontSize="sm">
                      {name
                        .replace(/ Underground Station$/, "")
                        .replace(/ Station$/, "")}
                    </Text>
                  ))}
                </Box>
              )}

              {/* Nearby bike points */}
              {stationDetails.bikePoints.length > 0 && (
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>
                    Nearby Bike Points
                  </Text>
                  {stationDetails.bikePoints.slice(0, 5).map((bp, i) => (
                    <HStack key={i} justify="space-between" fontSize="xs" mb={0.5}>
                      <Text lineClamp={1} maxW="60%">
                        {bp.name.replace(/^.+, /, "")}
                      </Text>
                      <HStack gap={1}>
                        <Badge colorPalette="green" size="sm">
                          {bp.nbBikes} bikes
                        </Badge>
                        <Text color="gray.400">{bp.distance}m</Text>
                      </HStack>
                    </HStack>
                  ))}
                </Box>
              )}

              {/* Coordinates */}
              <Text fontSize="xs" color="gray.400" mt={2}>
                {stationDetails.lat.toFixed(4)}, {stationDetails.lon.toFixed(4)}
              </Text>
            </Card.Body>
          </Card.Root>
        )}

        {!selectedStation && !selectedLine && !loading && (
          <Box textAlign="center" py={8}>
            <Text color="gray.400" fontSize="sm">
              Click a station on the map or ask the assistant to see details
            </Text>
          </Box>
        )}

        {/* Memory / Preferences */}
        {preferences.length > 0 && (
          <Card.Root>
            <Card.Body p={4}>
              <Heading size="xs" mb={2} color="purple.600">
                Your Preferences
              </Heading>
              {preferences.map((pref) => (
                <HStack key={pref.id} fontSize="xs" mb={1}>
                  <Badge colorPalette="purple" size="sm">
                    {pref.category}
                  </Badge>
                  <Text>{pref.preference}</Text>
                </HStack>
              ))}
            </Card.Body>
          </Card.Root>
        )}
      </VStack>
    </Box>
  );
}
