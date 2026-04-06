import { describe, it, expect } from "vitest";
import { groupToolCalls } from "@/lib/chatUtils";
import type { ToolCall } from "@/lib/types";

describe("groupToolCalls", () => {
  it("returns empty array for empty input", () => {
    expect(groupToolCalls([])).toEqual([]);
  });

  it("keeps a single call as a group with count 1", () => {
    const calls: ToolCall[] = [{ name: "find_route", result: "done" }];
    const groups = groupToolCalls(calls);
    expect(groups).toHaveLength(1);
    expect(groups[0].name).toBe("find_route");
    expect(groups[0].count).toBe(1);
    expect(groups[0].allDone).toBe(true);
    expect(groups[0].calls).toHaveLength(1);
  });

  it("groups consecutive same-name calls", () => {
    const calls: ToolCall[] = [
      { name: "find_route", result: "done" },
      { name: "find_route", result: "done" },
      { name: "find_route", result: "done" },
    ];
    const groups = groupToolCalls(calls);
    expect(groups).toHaveLength(1);
    expect(groups[0].count).toBe(3);
    expect(groups[0].allDone).toBe(true);
    expect(groups[0].calls).toHaveLength(3);
  });

  it("creates separate groups for different tool names", () => {
    const calls: ToolCall[] = [
      { name: "find_nearest_stations", result: "done" },
      { name: "find_route", result: "done" },
    ];
    const groups = groupToolCalls(calls);
    expect(groups).toHaveLength(2);
    expect(groups[0].name).toBe("find_nearest_stations");
    expect(groups[1].name).toBe("find_route");
  });

  it("creates separate groups when same name is non-consecutive", () => {
    const calls: ToolCall[] = [
      { name: "find_route", result: "done" },
      { name: "get_line_status", result: "done" },
      { name: "find_route", result: "done" },
    ];
    const groups = groupToolCalls(calls);
    expect(groups).toHaveLength(3);
    expect(groups[0].name).toBe("find_route");
    expect(groups[1].name).toBe("get_line_status");
    expect(groups[2].name).toBe("find_route");
  });

  it("sets allDone to false when any call in group lacks result", () => {
    const calls: ToolCall[] = [
      { name: "find_route", result: "done" },
      { name: "find_route" },
      { name: "find_route", result: "done" },
    ];
    const groups = groupToolCalls(calls);
    expect(groups).toHaveLength(1);
    expect(groups[0].allDone).toBe(false);
  });

  it("sets allDone to false when first call has no result", () => {
    const calls: ToolCall[] = [{ name: "find_route" }];
    const groups = groupToolCalls(calls);
    expect(groups[0].allDone).toBe(false);
  });
});
