"use client";

import { useEffect, useMemo, useState } from "react";
import { Box, Text, Spinner, Button, HStack } from "@chakra-ui/react";
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

export function MemoryGraphView() {
  const { sessionId, setMemoryLocations, setMainView } = useAppStore();
  const [memoryData, setMemoryData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);

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
      <HStack position="absolute" top={2} right={2} zIndex={10} gap={2}>
        <Button size="xs" variant="outline" onClick={handleShowOnMap}>
          Show locations on map
        </Button>
        <Button size="xs" variant="outline" onClick={refreshMemoryGraph}>
          Refresh
        </Button>
      </HStack>
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
