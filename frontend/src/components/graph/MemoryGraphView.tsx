"use client";

import { useEffect, useMemo, useState } from "react";
import { Box, Text, Spinner, Button, HStack, Flex, Badge } from "@chakra-ui/react";
import dynamic from "next/dynamic";
import { useAppStore } from "@/store/useAppStore";
import { getMemoryGraph, getMemoryLocations } from "@/lib/api";
import { NODE_COLORS } from "@/lib/graphStyles";
import type { GraphData } from "@/lib/types";

const InteractiveNvlWrapper = dynamic(
  () =>
    import("@neo4j-nvl/react").then((mod) => mod.InteractiveNvlWrapper),
  { ssr: false }
);

const MEMORY_LEGEND = [
  { type: "Conversation", color: NODE_COLORS.Conversation || "#6366F1" },
  { type: "Message", color: NODE_COLORS.Message || "#6366F1" },
  { type: "Entity", color: NODE_COLORS.Entity || "#2F9E44" },
  { type: "Preference", color: NODE_COLORS.Preference || "#F79767" },
  { type: "Trace", color: NODE_COLORS.ToolCall || "#D0BFFF" },
];

export function MemoryGraphView() {
  const { sessionId, setMemoryLocations, setMainView } = useAppStore();
  const [memoryData, setMemoryData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [locationMsg, setLocationMsg] = useState<string | null>(null);

  const refreshMemoryGraph = () => {
    setLoading(true);
    getMemoryGraph(sessionId)
      .then(setMemoryData)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refreshMemoryGraph();
  }, [sessionId]);

  const handleShowOnMap = async () => {
    try {
      const data = await getMemoryLocations(sessionId);
      if (data.locations.length > 0) {
        setMemoryLocations(data.locations);
        setMainView("map");
      } else {
        setLocationMsg("No geocoded locations found yet");
        setTimeout(() => setLocationMsg(null), 3000);
      }
    } catch (err) {
      console.error("Failed to load memory locations:", err);
    }
  };

  const nvlNodes = useMemo(() => {
    if (!memoryData?.nodes) return [];
    return memoryData.nodes.map((n) => ({
      id: n.id as string,
      caption: n.label as string,
      color: NODE_COLORS[(n.type as string) || ""] || "#888888",
      size: 10,
    }));
  }, [memoryData]);

  const nvlRels = useMemo(() => {
    if (!memoryData?.relationships) return [];
    return memoryData.relationships.map((r, i) => ({
      id: (r.id as string) || `rel-${i}`,
      from: r.source as string,
      to: r.target as string,
      caption: r.type as string,
    }));
  }, [memoryData]);

  if (loading) {
    return (
      <Box w="100%" h="100%" display="flex" alignItems="center" justifyContent="center">
        <Spinner size="lg" />
      </Box>
    );
  }

  if (!memoryData || memoryData.nodes.length === 0) {
    return (
      <Box w="100%" h="100%" display="flex" alignItems="center" justifyContent="center" bg="gray.50">
        <Text color="gray.500">Chat with the assistant to build memory</Text>
      </Box>
    );
  }

  return (
    <Box w="100%" h="100%" position="relative">
      {/* Legend */}
      <Flex position="absolute" top={2} left={2} zIndex={10} gap={1} flexWrap="wrap">
        {MEMORY_LEGEND.map(({ type, color }) => (
          <Badge
            key={type}
            style={{ backgroundColor: color }}
            color="white"
            fontSize="10px"
            px={1.5}
          >
            {type}
          </Badge>
        ))}
      </Flex>

      {/* Action buttons */}
      <HStack position="absolute" top={2} right={2} zIndex={10} gap={2}>
        <Button size="xs" variant="outline" onClick={handleShowOnMap}>
          Show locations on map
        </Button>
        <Button size="xs" variant="outline" onClick={refreshMemoryGraph}>
          Refresh
        </Button>
      </HStack>

      {/* Location feedback message */}
      {locationMsg && (
        <Box
          position="absolute"
          top={10}
          right={2}
          zIndex={10}
          bg="gray.700"
          color="white"
          px={3}
          py={1}
          borderRadius="md"
          fontSize="xs"
        >
          {locationMsg}
        </Box>
      )}

      <InteractiveNvlWrapper
        nodes={nvlNodes}
        rels={nvlRels}
        nvlOptions={{
          layout: "forceDirected",
          relationshipThreshold: 0.55,
        }}
        interactionOptions={{
          selectOnClick: true,
        }}
      />
    </Box>
  );
}
