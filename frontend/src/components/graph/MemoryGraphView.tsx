"use client";

import { useEffect, useMemo, useState } from "react";
import { Box, Text, Spinner } from "@chakra-ui/react";
import dynamic from "next/dynamic";
import { useAppStore } from "@/store/useAppStore";
import { getMemoryGraph } from "@/lib/api";
import { NODE_COLORS } from "@/lib/graphStyles";
import type { GraphData } from "@/lib/types";

const InteractiveNvlWrapper = dynamic(
  () =>
    import("@neo4j-nvl/react").then((mod) => mod.InteractiveNvlWrapper),
  { ssr: false }
);

export function MemoryGraphView() {
  const { sessionId } = useAppStore();
  const [memoryData, setMemoryData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getMemoryGraph(sessionId)
      .then(setMemoryData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sessionId]);

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
    <Box w="100%" h="100%">
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
