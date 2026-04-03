// Transport types

export interface Station {
  naptanId: string;
  name: string;
  lat: number;
  lon: number;
  zone: string | null;
  modes?: string[];
  lines?: LineRef[];
}

export interface LineRef {
  lineId: string;
  name: string;
  color: string;
}

export interface Line {
  lineId: string;
  name: string;
  modeName: string;
  color: string;
  stationCount?: number;
}

export interface BikePoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  nbDocks: number;
  nbBikes: number;
  nbEmptyDocks: number;
  distance?: number;
}

// Map types

export interface MapMarker {
  lat: number;
  lon: number;
  name: string;
  type: "station" | "bikepoint" | "route_stop" | "disruption";
  metadata?: Record<string, unknown>;
}

// Graph types

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface GraphRelationship {
  id?: string;
  source: string;
  target: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}

// Chat types

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  toolCalls?: ToolCall[];
  graphData?: GraphData;
  mapMarkers?: MapMarker[];
}

export interface ToolCall {
  name: string;
  arguments?: Record<string, unknown>;
  result?: string;
}

// SSE event types

export type SSEEvent =
  | { event: "token"; data: { content: string } }
  | { event: "tool_call"; data: { name: string; arguments: string } }
  | { event: "tool_result"; data: { name: string; result: string } }
  | { event: "done"; data: { session_id: string } }
  | { event: "error"; data: { error: string } };

// Memory types

export interface MemoryContext {
  short_term: Array<{
    id: string;
    role: string;
    content: string;
    timestamp?: string;
  }>;
  long_term: {
    entities: Array<{
      id: string;
      name: string;
      type: string;
      description?: string;
    }>;
    preferences: Array<{
      id: string;
      category: string;
      preference: string;
      context?: string;
    }>;
  };
  reasoning: Array<{
    id: string;
    task: string;
    outcome: string;
    steps: number;
  }>;
}

// Memory location (geocoded entity from memory)
export interface MemoryLocation {
  name: string;
  lat: number;
  lon: number;
  type: string;
  description?: string;
}
