"use client";

import { useEffect, useMemo, useCallback } from "react";
import { Box, Text } from "@chakra-ui/react";
import dynamic from "next/dynamic";
import { useAppStore } from "@/store/useAppStore";
import { getGraphNeighborhood } from "@/lib/api";
import { getNodeColor, getNodeSize } from "@/lib/graphStyles";
import type { GraphNode, GraphRelationship } from "@/lib/types";

// Dynamic import to avoid SSR issues with NVL
const InteractiveNvlWrapper = dynamic(
  () =>
    import("@neo4j-nvl/react").then((mod) => mod.InteractiveNvlWrapper),
  { ssr: false }
);

export function TransportGraphView() {
  const { graphData, setSelectedStation, panMapTo } = useAppStore();

  const nvlNodes = useMemo(() => {
    if (!graphData?.nodes) return [];
    return graphData.nodes.map((node: GraphNode) => ({
      id: node.id,
      caption: node.label,
      color: getNodeColor(node.type, node.properties),
      size: getNodeSize(node.type, node.properties),
    }));
  }, [graphData]);

  const nvlRelationships = useMemo(() => {
    if (!graphData?.relationships) return [];
    return graphData.relationships.map(
      (rel: GraphRelationship, i: number) => ({
        id: rel.id || `rel-${i}`,
        from: rel.source,
        to: rel.target,
        caption: rel.type,
      })
    );
  }, [graphData]);

  const handleNodeClick = useCallback(
    (node: { id: string }) => {
      const graphNode = graphData?.nodes.find((n) => n.id === node.id);
      if (graphNode?.type === "Station" && graphNode.properties) {
        const lat = graphNode.properties.lat as number;
        const lon = graphNode.properties.lon as number;
        if (lat && lon) {
          setSelectedStation({
            naptanId: graphNode.id,
            name: graphNode.label,
            lat,
            lon,
            zone: (graphNode.properties.zone as string) || null,
          });
          panMapTo(lat, lon, 15);
        }
      }
    },
    [graphData, setSelectedStation, panMapTo]
  );

  const handleNodeDoubleClick = useCallback(
    async (node: { id: string }) => {
      try {
        const neighborhood = await getGraphNeighborhood(node.id);
        const existingNodes = new Set(
          graphData?.nodes.map((n) => n.id) || []
        );
        const newNodes = (
          neighborhood.nodes as Array<{
            id: string;
            label: string;
            type: string;
            properties: Record<string, unknown>;
          }>
        )
          .filter((n) => !existingNodes.has(n.id as string))
          .map((n) => ({
            id: n.id as string,
            label: n.label as string,
            type: n.type as string,
            properties: n.properties as Record<string, unknown>,
          }));

        const newRels = (
          neighborhood.relationships as Array<{
            source: string;
            target: string;
            type: string;
          }>
        ).map((r) => ({
          source: r.source as string,
          target: r.target as string,
          type: r.type as string,
        }));

        useAppStore.getState().setGraphData({
          nodes: [...(graphData?.nodes || []), ...newNodes],
          relationships: [...(graphData?.relationships || []), ...newRels],
        });
      } catch (error) {
        console.error("Failed to expand node:", error);
      }
    },
    [graphData]
  );

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <Box
        w="100%"
        h="100%"
        display="flex"
        alignItems="center"
        justifyContent="center"
        bg="gray.50"
      >
        <Text color="gray.500">
          Ask the assistant about stations or lines to see the graph
        </Text>
      </Box>
    );
  }

  return (
    <Box w="100%" h="100%" position="relative">
      <InteractiveNvlWrapper
        nodes={nvlNodes}
        rels={nvlRelationships}
        nvlOptions={{
          layout: "force-directed",
          relationshipThreshold: 0.55,
        }}
        interactionOptions={{
          selectOnClick: true,
        }}
        nvlCallbacks={{
          onNodeClick: (node: unknown) =>
            handleNodeClick(node as { id: string }),
          onNodeDoubleClick: (node: unknown) =>
            handleNodeDoubleClick(node as { id: string }),
        }}
      />

      {/* Legend */}
      <Box
        position="absolute"
        bottom={4}
        left={4}
        bg="white"
        p={3}
        borderRadius="md"
        shadow="md"
        fontSize="xs"
      >
        <Text fontWeight="bold" mb={1}>
          Legend
        </Text>
        {[
          { color: "#DA7194", label: "Station" },
          { color: "#003688", label: "Line" },
          { color: "#2F9E44", label: "BikePoint" },
          { color: "#F79767", label: "Zone" },
        ].map(({ color, label }) => (
          <Box key={label} display="flex" alignItems="center" gap={1} mb={0.5}>
            <Box w={3} h={3} borderRadius="50%" bg={color} />
            <Text>{label}</Text>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
