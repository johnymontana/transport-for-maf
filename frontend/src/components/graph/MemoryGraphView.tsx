"use client";

import { useEffect, useMemo, useCallback, useState, useRef } from "react";
import { Box, Text, Spinner, Button, HStack, Flex, Badge, Heading } from "@chakra-ui/react";
import { useAppStore } from "@/store/useAppStore";
import { getMemoryGraph, getMemoryLocations } from "@/lib/api";
import { NODE_COLORS } from "@/lib/graphStyles";
import type { GraphData, GraphNode, GraphRelationship } from "@/lib/types";

// NVL node/relationship types
interface NvlNode {
  id: string;
  caption?: string;
  color?: string;
  size?: number;
  selected?: boolean;
}

interface NvlRelationship {
  id: string;
  from: string;
  to: string;
  caption?: string;
  color?: string;
  selected?: boolean;
}

interface SelectedElement {
  type: "node" | "relationship";
  data: GraphNode | GraphRelationship;
}

const MEMORY_LEGEND = [
  { type: "Conversation", color: NODE_COLORS.Conversation || "#6366F1" },
  { type: "Message", color: NODE_COLORS.Message || "#6366F1" },
  { type: "Entity", color: NODE_COLORS.Entity || "#2F9E44" },
  { type: "Preference", color: NODE_COLORS.Preference || "#F79767" },
  { type: "Trace", color: NODE_COLORS.ToolCall || "#D0BFFF" },
];

function getMemoryNodeColor(type: string): string {
  return NODE_COLORS[type] || "#888888";
}

export function MemoryGraphView() {
  const { sessionId, setMemoryLocations, setMainView } = useAppStore();
  const [memoryData, setMemoryData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [locationMsg, setLocationMsg] = useState<string | null>(null);

  const [selectedElement, setSelectedElement] = useState<SelectedElement | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRelId, setSelectedRelId] = useState<string | null>(null);

  const refreshMemoryGraph = () => {
    setLoading(true);
    setSelectedElement(null);
    setSelectedNodeId(null);
    setSelectedRelId(null);
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
        setTimeout(() => setLocationMsg(null), 4000);
      }
    } catch (err) {
      console.error("Failed to load memory locations:", err);
    }
  };

  // Transform to NVL format with selection highlighting
  const nvlNodes = useMemo(() => {
    if (!memoryData?.nodes) return [];
    return memoryData.nodes.map((n) => {
      const isSelected = selectedNodeId === n.id;
      return {
        id: n.id as string,
        caption: n.label as string,
        color: isSelected ? "#E53E3E" : getMemoryNodeColor(n.type as string),
        size: isSelected ? 14 : 10,
        selected: isSelected,
      };
    });
  }, [memoryData, selectedNodeId]);

  const nvlRels = useMemo(() => {
    if (!memoryData?.relationships) return [];
    return memoryData.relationships.map((r, i) => {
      const relId = (r.id as string) || `rel-${i}`;
      const isSelected = selectedRelId === relId;
      return {
        id: relId,
        from: r.source as string,
        to: r.target as string,
        caption: r.type as string,
        color: isSelected ? "#E53E3E" : undefined,
        selected: isSelected,
      };
    });
  }, [memoryData, selectedRelId]);

  const handleNodeClick = useCallback(
    (node: NvlNode) => {
      const graphNode = memoryData?.nodes.find((n) => n.id === node.id);
      if (!graphNode) return;
      setSelectedElement({ type: "node", data: graphNode });
      setSelectedNodeId(node.id);
      setSelectedRelId(null);
    },
    [memoryData]
  );

  const handleRelationshipClick = useCallback(
    (rel: NvlRelationship) => {
      const graphRel = memoryData?.relationships.find(
        (r, i) => (r.id || `rel-${i}`) === rel.id
      );
      if (graphRel) {
        setSelectedElement({ type: "relationship", data: graphRel });
        setSelectedRelId(rel.id);
        setSelectedNodeId(null);
      }
    },
    [memoryData]
  );

  const handleCanvasClick = useCallback(() => {
    setSelectedElement(null);
    setSelectedNodeId(null);
    setSelectedRelId(null);
  }, []);

  const getNodeLabel = useCallback(
    (nodeId: string) => {
      const node = memoryData?.nodes.find((n) => n.id === nodeId);
      return node?.label || nodeId;
    },
    [memoryData]
  );

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
      <Flex
        position="absolute"
        top={2}
        left={2}
        zIndex={10}
        gap={1}
        flexWrap="wrap"
        maxW={{ base: "100%", md: "70%" }}
        bg="white"
        borderRadius="md"
        p={{ base: 1, md: 1.5 }}
        shadow="sm"
        borderWidth="1px"
        borderColor="gray.200"
      >
        {MEMORY_LEGEND.map(({ type, color }) => (
          <Badge
            key={type}
            style={{ backgroundColor: color }}
            color="white"
            fontSize="10px"
            px={{ base: 1, md: 1.5 }}
          >
            {type}
          </Badge>
        ))}
      </Flex>

      {/* Action buttons */}
      <HStack position="absolute" top={2} right={2} zIndex={10} gap={2}>
        <Button size="xs" variant="outline" bg="white" onClick={handleShowOnMap}>
          Show locations on map
        </Button>
        <Button size="xs" variant="outline" bg="white" onClick={refreshMemoryGraph}>
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

      {/* Properties Panel */}
      {selectedElement && (
        <Box
          position="absolute"
          top={12}
          right={2}
          zIndex={10}
          bg="white"
          borderRadius="md"
          p={3}
          maxW="280px"
          maxH="400px"
          overflow="auto"
          shadow="md"
          borderWidth="1px"
          borderColor="gray.200"
        >
          <Flex justify="space-between" align="center" mb={2}>
            <Heading size="sm">
              {selectedElement.type === "node" ? "Node" : "Relationship"}
            </Heading>
            <Box
              as="button"
              onClick={handleCanvasClick}
              cursor="pointer"
              p={1}
              borderRadius="sm"
              _hover={{ bg: "gray.100" }}
              fontSize="sm"
            >
              ✕
            </Box>
          </Flex>

          {selectedElement.type === "node" && (() => {
            const node = selectedElement.data as GraphNode;
            return (
              <Box>
                <Flex gap={1} mb={2} flexWrap="wrap">
                  <Badge
                    size="sm"
                    style={{
                      backgroundColor: getMemoryNodeColor(node.type),
                      color: "white",
                    }}
                  >
                    {node.type}
                  </Badge>
                </Flex>
                <Text fontSize="sm" fontWeight="bold" mb={2}>
                  {node.label}
                </Text>
                {node.properties && Object.keys(node.properties).length > 0 && (
                  <Box>
                    <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>
                      Properties
                    </Text>
                    {Object.entries(node.properties).map(([key, value]) => (
                      <Box
                        key={key}
                        bg="gray.50"
                        p={1}
                        borderRadius="sm"
                        fontSize="xs"
                        mb={1}
                      >
                        <Text fontWeight="medium" color="gray.600">
                          {key}
                        </Text>
                        <Text color="gray.800" wordBreak="break-word">
                          {typeof value === "object"
                            ? JSON.stringify(value, null, 2)
                            : String(value)}
                        </Text>
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            );
          })()}

          {selectedElement.type === "relationship" && (() => {
            const rel = selectedElement.data as GraphRelationship;
            return (
              <Box>
                <Badge size="sm" colorPalette="gray" mb={2}>
                  {rel.type}
                </Badge>
                <Box fontSize="xs" mb={1}>
                  <Text fontWeight="bold" color="gray.500">From</Text>
                  <Text>{getNodeLabel(rel.source)}</Text>
                </Box>
                <Box fontSize="xs" mb={1}>
                  <Text fontWeight="bold" color="gray.500">To</Text>
                  <Text>{getNodeLabel(rel.target)}</Text>
                </Box>
                {rel.properties && Object.keys(rel.properties).length > 0 && (
                  <Box mt={2}>
                    <Text fontSize="xs" fontWeight="bold" color="gray.500" mb={1}>
                      Properties
                    </Text>
                    {Object.entries(rel.properties).map(([key, value]) => (
                      <Box
                        key={key}
                        bg="gray.50"
                        p={1}
                        borderRadius="sm"
                        fontSize="xs"
                        mb={1}
                      >
                        <Text fontWeight="medium" color="gray.600">
                          {key}
                        </Text>
                        <Text color="gray.800" wordBreak="break-word">
                          {typeof value === "object"
                            ? JSON.stringify(value, null, 2)
                            : String(value)}
                        </Text>
                      </Box>
                    ))}
                  </Box>
                )}
              </Box>
            );
          })()}
        </Box>
      )}

      {/* Instructions */}
      <Box
        position="absolute"
        bottom={2}
        left={2}
        zIndex={10}
        bg="white"
        borderRadius="md"
        px={2}
        py={1}
        shadow="sm"
        borderWidth="1px"
        borderColor="gray.200"
        opacity={0.8}
      >
        <Text fontSize="xs" color="gray.500">
          Scroll to zoom · Drag to pan · Click to inspect
        </Text>
      </Box>

      {/* Graph */}
      <Box h="100%" w="100%">
        <NvlGraph
          nodes={nvlNodes}
          relationships={nvlRels}
          onNodeClick={handleNodeClick}
          onRelationshipClick={handleRelationshipClick}
          onCanvasClick={handleCanvasClick}
        />
      </Box>
    </Box>
  );
}

// Separate component for NVL — uses useState dynamic import for reliable initialization
function NvlGraph({
  nodes,
  relationships,
  onNodeClick,
  onRelationshipClick,
  onCanvasClick,
}: {
  nodes: NvlNode[];
  relationships: NvlRelationship[];
  onNodeClick: (node: NvlNode) => void;
  onRelationshipClick: (rel: NvlRelationship) => void;
  onCanvasClick: () => void;
}) {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [NvlComponent, setNvlComponent] = useState<React.ComponentType<any> | null>(null);
  const [isReady, setIsReady] = useState(false);
  const nvlRef = useRef<any>(null);

  useEffect(() => {
    import("@neo4j-nvl/react").then((mod) => {
      setNvlComponent(() => mod.InteractiveNvlWrapper);
    });
  }, []);

  useEffect(() => {
    if (NvlComponent && nodes.length > 0) {
      const timer = setTimeout(() => setIsReady(true), 100);
      return () => clearTimeout(timer);
    }
  }, [NvlComponent, nodes.length]);

  if (!NvlComponent) {
    return (
      <Flex h="100%" align="center" justify="center">
        <Text color="gray.500">Loading graph...</Text>
      </Flex>
    );
  }

  return (
    <NvlComponent
      ref={nvlRef}
      nodes={nodes}
      rels={relationships}
      nvlOptions={{
        layout: "d3Force",
        initialZoom: 1,
        minZoom: 0.1,
        maxZoom: 5,
        relationshipThickness: 2,
        disableTelemetry: true,
      }}
      mouseEventCallbacks={{
        onNodeClick: (node: NvlNode) => onNodeClick(node),
        onRelationshipClick: (rel: NvlRelationship) => onRelationshipClick(rel),
        onCanvasClick: () => onCanvasClick(),
        onZoom: isReady,
        onPan: isReady,
        onDrag: isReady,
      }}
      style={{ width: "100%", height: "100%" }}
    />
  );
}
