"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Box,
  Flex,
  VStack,
  HStack,
  Input,
  Button,
  Text,
  Card,
  Badge,
  Spinner,
  Heading,
} from "@chakra-ui/react";
import ReactMarkdown from "react-markdown";
import { streamChat } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import type { Message, MapMarker, GraphData } from "@/lib/types";

export function ChatPanel() {
  const { sessionId, setMapMarkers, setGraphData, panMapTo, setMainView } =
    useAppStore();

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I'm TfL Explorer, your London transport assistant. I can help you find stations, plan routes, check line status, and find bike hire points. What would you like to know?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const processToolResult = (resultData: unknown) => {
    try {
      // Handle both string and already-parsed object
      const result =
        typeof resultData === "string" ? JSON.parse(resultData) : resultData;
      if (!result || typeof result !== "object") return;

      // Update map markers from tool results
      if (result.map_markers && result.map_markers.length > 0) {
        const markers: MapMarker[] = result.map_markers;
        useAppStore.getState().addMapMarkers(markers);
        // Pan to first marker
        if (markers[0]) {
          panMapTo(markers[0].lat, markers[0].lon, 14);
          setMainView("map");
        }
        // Auto-select first station for the detail panel
        const firstStation = markers.find((m) => m.type === "station" || m.type === "route_stop");
        if (firstStation) {
          useAppStore.getState().setSelectedStation({
            naptanId: (firstStation.metadata?.naptanId as string) || "",
            name: firstStation.name,
            lat: firstStation.lat,
            lon: firstStation.lon,
            zone: (firstStation.metadata?.zone as string) || null,
          });
        }
      }

      // Update graph data from tool results
      if (
        result.graph_data &&
        (result.graph_data.nodes?.length > 0 ||
          result.graph_data.relationships?.length > 0)
      ) {
        const existing = useAppStore.getState().graphData;
        if (existing) {
          // Merge with existing graph data
          const existingNodeIds = new Set(existing.nodes.map((n) => n.id));
          const newNodes = result.graph_data.nodes.filter(
            (n: { id: string }) => !existingNodeIds.has(n.id)
          );
          setGraphData({
            nodes: [...existing.nodes, ...newNodes],
            relationships: [
              ...existing.relationships,
              ...result.graph_data.relationships,
            ],
          });
        } else {
          setGraphData(result.graph_data as GraphData);
        }
      }

      // Handle route coordinates for map line
      if (result.route && Array.isArray(result.route)) {
        const coords: [number, number][] = result.route.map(
          (s: { lat: number; lon: number }) => [s.lon, s.lat]
        );
        useAppStore.getState().setRouteCoordinates(coords);
        // Zoom to fit route
        if (result.route.length > 0) {
          const lats = result.route.map((s: { lat: number }) => s.lat);
          const lons = result.route.map((s: { lon: number }) => s.lon);
          const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
          const centerLon = (Math.min(...lons) + Math.max(...lons)) / 2;
          panMapTo(centerLat, centerLon, 13);
          setMainView("map");
        }
      }
    } catch {
      // Tool result may not be JSON
    }
  };

  const handleSend = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const assistantId = `assistant-${Date.now()}`;
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isStreaming: true,
      toolCalls: [],
    };

    setMessages((prev) => [...prev, assistantMessage]);

    try {
      for await (const event of streamChat(
        userMessage.content,
        sessionId
      )) {
        const data = event.data;

        if (event.event === "token" && data.content) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + data.content }
                : m
            )
          );
        }

        if (event.event === "tool_call" && data.name) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    toolCalls: [
                      ...(m.toolCalls || []),
                      {
                        name: data.name as string,
                        arguments: data.arguments as Record<string, unknown>,
                      },
                    ],
                  }
                : m
            )
          );
        }

        if (event.event === "tool_result" && data.result) {
          processToolResult(data.result);
          // Match result to the first unresolved tool call (by position)
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              let matched = false;
              return {
                ...m,
                toolCalls: m.toolCalls?.map((tc) => {
                  if (!tc.result && !matched) {
                    matched = true;
                    return { ...tc, result: data.result as string };
                  }
                  return tc;
                }),
              };
            })
          );
        }

        if (event.event === "done") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, isStreaming: false } : m
            )
          );
        }

        if (event.event === "error") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: `Error: ${data.error}`,
                    isStreaming: false,
                  }
                : m
            )
          );
        }
      }
    } catch (error) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m
        )
      );
      inputRef.current?.focus();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  const examplePrompts = [
    "Find stations near Big Ben",
    "Show me the Northern Line",
    "Route from Tower of London to Buckingham Palace",
    "Find bike points near Waterloo",
    "Are there any disruptions?",
  ];

  return (
    <Flex direction="column" h="100%" bg="gray.50" borderRight={{ base: "none", lg: "1px solid" }} borderColor="gray.200">
      <Box p={4} borderBottom="1px solid" borderColor="gray.200" bg="white">
        <Heading as="h1" size="md" color="blue.700">
          TfL Explorer
        </Heading>
        <Text fontSize="xs" color="gray.500">
          London Transport Assistant
        </Text>
      </Box>

      {/* Messages */}
      <Box flex={1} overflowY="auto" p={4}>
        <VStack gap={4} align="stretch">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {/* Suggestion prompts (inline after messages) */}
          {messages.length <= 2 && (
            <Flex gap={2} flexWrap="wrap">
              {examplePrompts.map((prompt, i) => (
                <Button
                  key={i}
                  size="xs"
                  variant="outline"
                  colorPalette="blue"
                  onClick={() => handleSend(prompt)}
                  whiteSpace="normal"
                  textAlign="left"
                  height="auto"
                  py={1.5}
                >
                  {prompt}
                </Button>
              ))}
            </Flex>
          )}

          <div ref={messagesEndRef} />
        </VStack>
      </Box>

      {/* Input */}
      <Box as="form" onSubmit={handleSubmit} p={4} bg="white" borderTop="1px solid" borderColor="gray.200">
        <HStack gap={2}>
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about stations, routes, lines..."
            size="md"
            disabled={isLoading}
          />
          <Button
            type="submit"
            colorPalette="blue"
            size="md"
            disabled={isLoading || !input.trim()}
          >
            {isLoading ? <Spinner size="sm" /> : "Send"}
          </Button>
        </HStack>
      </Box>
    </Flex>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <Flex justify={isUser ? "flex-end" : "flex-start"}>
      <Card.Root
        maxW="90%"
        bg={isUser ? "blue.600" : "white"}
        color={isUser ? "white" : "gray.800"}
        shadow="sm"
        size="sm"
      >
        <Card.Body p={3}>
          {/* Tool calls */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <VStack align="stretch" gap={1} mb={2}>
              {message.toolCalls.map((tc, i) => (
                <Box
                  key={i}
                  bg={isUser ? "blue.700" : "gray.100"}
                  p={1.5}
                  borderRadius="md"
                  fontSize="xs"
                >
                  <HStack>
                    <Badge colorPalette="purple" size="sm">
                      {tc.name}
                    </Badge>
                    {!tc.result && <Spinner size="xs" />}
                    {tc.result && (
                      <Text color="green.600" fontSize="xs">
                        done
                      </Text>
                    )}
                  </HStack>
                </Box>
              ))}
            </VStack>
          )}

          {/* Content */}
          {message.content ? (
            <Box
              fontSize="sm"
              css={{
                "& p": { marginBottom: "0.5em" },
                "& p:last-child": { marginBottom: 0 },
                "& ul, & ol": { paddingLeft: "1.5em", marginBottom: "0.5em" },
                "& code": {
                  background: isUser ? "rgba(255,255,255,0.2)" : "#f0f0f0",
                  padding: "0.1em 0.3em",
                  borderRadius: "3px",
                  fontSize: "0.9em",
                },
              }}
            >
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </Box>
          ) : message.isStreaming ? (
            <HStack gap={2}>
              <Text
                fontSize="sm"
                color={isUser ? "blue.200" : "gray.400"}
                css={{
                  "&::after": {
                    content: "'...'",
                    animation: "thinking 1.5s infinite",
                  },
                  "@keyframes thinking": {
                    "0%": { content: "'.'" },
                    "33%": { content: "'..'" },
                    "66%": { content: "'...'" },
                  },
                }}
              >
                Thinking
              </Text>
            </HStack>
          ) : null}
        </Card.Body>
      </Card.Root>
    </Flex>
  );
}
