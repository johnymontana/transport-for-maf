"use client";

import { useEffect, useMemo, useCallback, useState, useRef } from "react";
import { Box, Text, Flex, Badge, Heading, Spinner } from "@chakra-ui/react";
import { useAppStore } from "@/store/useAppStore";
import { getGraphNeighborhood } from "@/lib/api";
import { getNodeColor, getNodeSize } from "@/lib/graphStyles";
import type { GraphNode, GraphRelationship } from "@/lib/types";

// NVL node/relationship types for internal use
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

export function TransportGraphView() {
  const { graphData, setSelectedStation, panMapTo } = useAppStore();

  const [selectedElement, setSelectedElement] =
    useState<SelectedElement | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRelId, setSelectedRelId] = useState<string | null>(null);
  const [isExpanding, setIsExpanding] = useState(false);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(
    new Set()
  );

  // Reset selection state when graph data changes from a new query
  useEffect(() => {
    setSelectedElement(null);
    setSelectedNodeId(null);
    setSelectedRelId(null);
    setExpandedNodeIds(new Set());
  }, [graphData]);

  // Transform graph data to NVL format
  const nvlNodes = useMemo(() => {
    if (!graphData?.nodes) return [];
    return graphData.nodes.map((node: GraphNode) => {
      const isSelected = selectedNodeId === node.id;
      const isExpanded = expandedNodeIds.has(node.id);
      const baseSize = getNodeSize(node.type, node.properties);
      return {
        id: node.id,
        caption: node.label,
        color: isSelected
          ? "#E53E3E"
          : isExpanded
            ? "#38A169"
            : getNodeColor(node.type, node.properties),
        size: isSelected ? baseSize * 1.3 : baseSize,
        selected: isSelected,
      };
    });
  }, [graphData, selectedNodeId, expandedNodeIds]);

  const nvlRelationships = useMemo(() => {
    if (!graphData?.relationships) return [];
    return graphData.relationships.map(
      (rel: GraphRelationship, i: number) => {
        const isSelected = selectedRelId === (rel.id || `rel-${i}`);
        return {
          id: rel.id || `rel-${i}`,
          from: rel.source,
          to: rel.target,
          caption: rel.type,
          color: isSelected ? "#E53E3E" : undefined,
          selected: isSelected,
        };
      }
    );
  }, [graphData, selectedRelId]);

  const handleNodeClick = useCallback(
    (node: NvlNode) => {
      const graphNode = graphData?.nodes.find((n) => n.id === node.id);
      if (!graphNode) return;

      setSelectedElement({ type: "node", data: graphNode });
      setSelectedNodeId(node.id);
      setSelectedRelId(null);

      // If it's a station, also update the map
      if (graphNode.type === "Station" && graphNode.properties) {
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
    async (node: NvlNode) => {
      if (!graphData || isExpanding) return;
      if (expandedNodeIds.has(node.id)) return;

      setIsExpanding(true);
      try {
        const neighborhood = await getGraphNeighborhood(node.id);

        const existingNodeIds = new Set(graphData.nodes.map((n) => n.id));
        const newNodes = neighborhood.nodes.filter(
          (n) => !existingNodeIds.has(n.id)
        );

        const existingRelIds = new Set(
          graphData.relationships.map((r, i) => r.id || `rel-${i}`)
        );
        const newRels = neighborhood.relationships.filter(
          (r) => !existingRelIds.has(r.id || "")
        );

        useAppStore.getState().setGraphData({
          nodes: [...graphData.nodes, ...newNodes],
          relationships: [...graphData.relationships, ...newRels],
        });

        setExpandedNodeIds((prev) => {
          const next = new Set(prev);
          next.add(node.id);
          return next;
        });
      } catch (error) {
        console.error("Failed to expand node:", error);
      } finally {
        setIsExpanding(false);
      }
    },
    [graphData, isExpanding, expandedNodeIds]
  );

  const handleRelationshipClick = useCallback(
    (rel: NvlRelationship) => {
      const graphRel = graphData?.relationships.find(
        (r, i) => (r.id || `rel-${i}`) === rel.id
      );
      if (graphRel) {
        setSelectedElement({ type: "relationship", data: graphRel });
        setSelectedRelId(rel.id);
        setSelectedNodeId(null);
      }
    },
    [graphData]
  );

  const handleCanvasClick = useCallback(() => {
    setSelectedElement(null);
    setSelectedNodeId(null);
    setSelectedRelId(null);
  }, []);

  // Helper to resolve a node ID to its label
  const getNodeLabel = useCallback(
    (nodeId: string) => {
      const node = graphData?.nodes.find((n) => n.id === nodeId);
      return node?.label || nodeId;
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

  // Collect unique node types for legend
  const nodeTypes = Array.from(new Set(graphData.nodes.map((n) => n.type)));

  return (
    <Box w="100%" h="100%" position="relative">
      {/* Legend */}
      <Flex
        position="absolute"
        top={2}
        left={2}
        zIndex={10}
        bg="white"
        borderRadius="md"
        p={2}
        gap={1}
        flexWrap="wrap"
        maxW="200px"
        shadow="sm"
        borderWidth="1px"
        borderColor="gray.200"
      >
        {nodeTypes.map((type) => (
          <Badge
            key={type}
            size="sm"
            style={{
              backgroundColor: getNodeColor(type),
              color: type === "Zone" ? "black" : "white",
            }}
          >
            {type}
          </Badge>
        ))}
      </Flex>

      {/* Properties Panel */}
      {selectedElement && (
        <Box
          position="absolute"
          top={2}
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
              onClick={() => {
                setSelectedElement(null);
                setSelectedNodeId(null);
                setSelectedRelId(null);
              }}
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
                      backgroundColor: getNodeColor(node.type, node.properties),
                      color: node.type === "Zone" ? "black" : "white",
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
          Scroll to zoom · Drag to pan · Click to inspect · Double-click to
          expand
        </Text>
      </Box>

      {/* Loading indicator for expansion */}
      {isExpanding && (
        <Flex
          position="absolute"
          top="50%"
          left="50%"
          transform="translate(-50%, -50%)"
          zIndex={20}
          bg="white"
          borderRadius="md"
          p={3}
          shadow="md"
          borderWidth="1px"
          borderColor="gray.200"
          align="center"
          gap={2}
        >
          <Spinner size="sm" />
          <Text fontSize="sm">Expanding node...</Text>
        </Flex>
      )}

      {/* Graph */}
      <Box h="100%" w="100%">
        <NvlGraph
          nodes={nvlNodes}
          relationships={nvlRelationships}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
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
  onNodeDoubleClick,
  onRelationshipClick,
  onCanvasClick,
}: {
  nodes: NvlNode[];
  relationships: NvlRelationship[];
  onNodeClick: (node: NvlNode) => void;
  onNodeDoubleClick: (node: NvlNode) => void;
  onRelationshipClick: (rel: NvlRelationship) => void;
  onCanvasClick: () => void;
}) {
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [NvlComponent, setNvlComponent] =
    useState<React.ComponentType<any> | null>(null);
  const [isReady, setIsReady] = useState(false);
  const nvlRef = useRef<any>(null);

  useEffect(() => {
    import("@neo4j-nvl/react").then((mod) => {
      setNvlComponent(() => mod.InteractiveNvlWrapper);
    });
  }, []);

  // Allow interactions after NVL initializes
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
        onNodeDoubleClick: (node: NvlNode) => onNodeDoubleClick(node),
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
