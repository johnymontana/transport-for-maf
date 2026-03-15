"use client";

import { useEffect, useState } from "react";
import { Box, HStack, Text, Badge } from "@chakra-ui/react";
import { getLines, getLineGraph } from "@/lib/api";
import { TFL_LINE_COLORS } from "@/lib/graphStyles";
import { useAppStore } from "@/store/useAppStore";
import type { GraphNode } from "@/lib/types";

interface LineInfo {
  lineId: string;
  name: string;
  color: string;
  stationCount?: number;
}

export function LineStatusBanner() {
  const [lines, setLines] = useState<LineInfo[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const {
    selectedLine,
    setSelectedLine,
    setMapMarkers,
    setGraphData,
    panMapTo,
    clearSelection,
  } = useAppStore();

  useEffect(() => {
    getLines()
      .then((data) => setLines(data.lines))
      .catch(() => {});
  }, []);

  const handleLineClick = async (line: LineInfo) => {
    // Toggle off if already selected
    if (selectedLine?.lineId === line.lineId) {
      clearSelection();
      return;
    }

    setLoading(line.lineId);
    try {
      // Set selected line in store
      setSelectedLine({
        lineId: line.lineId,
        name: line.name,
        modeName: "",
        color: TFL_LINE_COLORS[line.lineId] || line.color || "#666",
      });

      // Fetch full line graph (stations, zones, bike points)
      const graphData = await getLineGraph(line.lineId);

      if (graphData.nodes.length === 0) return;

      // Set graph data directly (backend builds the full subgraph)
      setGraphData(graphData);

      // Set map markers from station nodes
      const stationNodes = graphData.nodes.filter(
        (n: GraphNode) => n.type === "Station"
      );
      setMapMarkers(
        stationNodes.map((n: GraphNode) => ({
          lat: n.properties?.lat as number,
          lon: n.properties?.lon as number,
          name: n.label,
          type: "station" as const,
          metadata: {
            zone: n.properties?.zone,
            sequence: n.properties?.sequence,
          },
        }))
      );

      // Zoom map to fit the line
      const lats = stationNodes.map((n: GraphNode) => n.properties?.lat as number);
      const lons = stationNodes.map((n: GraphNode) => n.properties?.lon as number);
      const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
      const centerLon = (Math.min(...lons) + Math.max(...lons)) / 2;
      panMapTo(centerLat, centerLon, 11);
    } catch (err) {
      console.error("Failed to load line stations:", err);
    } finally {
      setLoading(null);
    }
  };

  if (lines.length === 0) {
    return (
      <Box
        bg="gray.800"
        color="white"
        px={4}
        py={1.5}
        fontSize="xs"
        textAlign="center"
      >
        TfL Explorer - Loading lines...
      </Box>
    );
  }

  return (
    <Box bg="gray.800" px={4} py={1.5} overflow="hidden">
      <HStack gap={3} overflowX="auto" css={{ "&::-webkit-scrollbar": { display: "none" } }}>
        <Text color="gray.400" fontSize="xs" flexShrink={0} fontWeight="bold">
          Lines:
        </Text>
        {lines.map((line) => {
          const isSelected = selectedLine?.lineId === line.lineId;
          const isLoading = loading === line.lineId;
          return (
            <Badge
              key={line.lineId}
              bg={TFL_LINE_COLORS[line.lineId] || line.color || "gray.600"}
              color={
                ["circle", "hammersmith-city", "waterloo-city"].includes(line.lineId)
                  ? "black"
                  : "white"
              }
              fontSize="10px"
              px={2}
              py={0.5}
              borderRadius="sm"
              flexShrink={0}
              cursor="pointer"
              opacity={isLoading ? 0.6 : 1}
              outline={isSelected ? "2px solid white" : "none"}
              outlineOffset="1px"
              _hover={{ opacity: 0.8 }}
              onClick={() => handleLineClick(line)}
            >
              {line.name}
            </Badge>
          );
        })}
      </HStack>
    </Box>
  );
}
