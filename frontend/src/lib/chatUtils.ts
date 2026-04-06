import { v4 as uuid } from "uuid";
import type { ToolCall } from "./types";

export interface ToolCallGroup {
  name: string;
  count: number;
  allDone: boolean;
  calls: ToolCall[];
}

/**
 * Groups consecutive tool calls of the same type into a single display row.
 * E.g., 10 sequential `find_route` calls become one group with count=10.
 */
export function groupToolCalls(calls: ToolCall[]): ToolCallGroup[] {
  const groups: ToolCallGroup[] = [];
  for (const tc of calls) {
    const last = groups[groups.length - 1];
    if (last && last.name === tc.name) {
      last.count++;
      last.calls.push(tc);
      if (!tc.result) last.allDone = false;
    } else {
      groups.push({
        name: tc.name,
        count: 1,
        allDone: !!tc.result,
        calls: [tc],
      });
    }
  }
  return groups;
}

/**
 * Gets or creates a session ID from sessionStorage.
 * Falls back to a fresh UUID if storage is unavailable.
 */
export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return uuid();
  try {
    const stored = sessionStorage.getItem("tfl-session-id");
    if (stored) return stored;
    const id = uuid();
    sessionStorage.setItem("tfl-session-id", id);
    return id;
  } catch {
    return uuid();
  }
}
