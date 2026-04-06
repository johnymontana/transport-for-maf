import { describe, it, expect, beforeEach, vi } from "vitest";
import { getOrCreateSessionId } from "@/lib/chatUtils";

describe("getOrCreateSessionId", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("generates a UUID and stores it in sessionStorage", () => {
    const id = getOrCreateSessionId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    );
    expect(sessionStorage.getItem("tfl-session-id")).toBe(id);
  });

  it("returns the same ID on repeated calls", () => {
    const id1 = getOrCreateSessionId();
    const id2 = getOrCreateSessionId();
    expect(id1).toBe(id2);
  });

  it("returns a stored session ID from sessionStorage", () => {
    sessionStorage.setItem("tfl-session-id", "test-session-123");
    const id = getOrCreateSessionId();
    expect(id).toBe("test-session-123");
  });

  it("falls back to a fresh UUID when sessionStorage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });

    const id = getOrCreateSessionId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    );

    vi.restoreAllMocks();
  });
});
