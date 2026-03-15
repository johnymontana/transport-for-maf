/**
 * API client for the TfL Explorer backend.
 */

import type { GraphData, GraphNode, GraphRelationship, Line, MapMarker, MemoryContext, Station } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Stream a chat message and receive SSE responses.
 */
export async function* streamChat(
  message: string,
  sessionId?: string,
  userId?: string
): AsyncGenerator<{ event: string; data: Record<string, unknown> }> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      user_id: userId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.slice(6).trim();
        continue;
      }
      if (line.startsWith("data:")) {
        const dataStr = line.slice(5).trim();
        if (dataStr) {
          try {
            const data = JSON.parse(dataStr);
            yield { event: currentEvent, data };
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  }
}

// --- Transport endpoints ---

export async function getStations(): Promise<{ stations: Station[] }> {
  const resp = await fetch(`${API_BASE}/stations`);
  if (!resp.ok) throw new Error("Failed to get stations");
  return resp.json();
}

export async function getStationDetails(naptanId: string): Promise<Station & {
  bikePoints: Array<{ name: string; distance: number; nbBikes: number; nbDocks: number; lat: number; lon: number }>;
  interchanges: string[];
}> {
  const resp = await fetch(`${API_BASE}/stations/${naptanId}`);
  if (!resp.ok) throw new Error("Failed to get station details");
  return resp.json();
}

export async function getNearbyStations(
  lat: number,
  lon: number,
  radius = 1000,
  limit = 10
): Promise<{ stations: (Station & { distance: number })[] }> {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    radius: radius.toString(),
    limit: limit.toString(),
  });
  const resp = await fetch(`${API_BASE}/stations/nearby?${params}`);
  if (!resp.ok) throw new Error("Failed to get nearby stations");
  return resp.json();
}

export async function getLines(): Promise<{ lines: Line[] }> {
  const resp = await fetch(`${API_BASE}/lines`);
  if (!resp.ok) throw new Error("Failed to get lines");
  return resp.json();
}

export async function getLineStations(
  lineId: string
): Promise<{ stations: (Station & { sequence: number; lineName: string; lineColor: string })[] }> {
  const resp = await fetch(`${API_BASE}/lines/${lineId}/stations`);
  if (!resp.ok) throw new Error("Failed to get line stations");
  return resp.json();
}

export async function getLineGraph(lineId: string): Promise<GraphData> {
  const resp = await fetch(`${API_BASE}/lines/${lineId}/graph`);
  if (!resp.ok) throw new Error("Failed to get line graph");
  return resp.json();
}

// --- Memory endpoints ---

export async function getMemoryContext(
  sessionId: string,
  query?: string
): Promise<MemoryContext> {
  const params = new URLSearchParams({ session_id: sessionId });
  if (query) params.append("query", query);
  const resp = await fetch(`${API_BASE}/memory/context?${params}`);
  if (!resp.ok) throw new Error("Failed to get memory context");
  return resp.json();
}

export async function getMemoryGraph(sessionId: string): Promise<GraphData> {
  const params = new URLSearchParams({ session_id: sessionId });
  const resp = await fetch(`${API_BASE}/memory/graph?${params}`);
  if (!resp.ok) throw new Error("Failed to get memory graph");
  return resp.json();
}

export async function getPreferences(
  sessionId: string
): Promise<{
  preferences: Array<{
    id: string;
    category: string;
    preference: string;
    context?: string;
  }>;
}> {
  const params = new URLSearchParams({ session_id: sessionId });
  const resp = await fetch(`${API_BASE}/memory/preferences?${params}`);
  if (!resp.ok) throw new Error("Failed to get preferences");
  return resp.json();
}

// --- Graph endpoints ---

export async function getGraphNeighborhood(nodeId: string): Promise<{
  center: GraphNode;
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}> {
  const resp = await fetch(`${API_BASE}/graph/neighborhood/${nodeId}`);
  if (!resp.ok) throw new Error("Failed to get graph neighborhood");
  return resp.json();
}

// --- Health ---

export async function checkHealth(): Promise<{ status: string; database: string }> {
  const resp = await fetch(`${API_BASE}/health`);
  return resp.json();
}
