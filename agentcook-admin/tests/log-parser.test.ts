import { describe, it, expect } from "vitest";
import {
  parseLogLine,
  shouldShow,
  makeMockLogStream,
  LEVEL_RANK,
} from "@/views/monitoring/logTypes";

describe("log line parser · Day 31", () => {
  it("parses structlog JSON shape", () => {
    const line = parseLogLine(
      '{"level":"WARN","ts":"2026-06-07T10:00:00Z","msg":"rate limit"}',
    );
    expect(line?.level).toBe("WARN");
    expect(line?.message).toBe("rate limit");
    expect(line?.ts).toBe("2026-06-07T10:00:00Z");
  });

  it("parses prefixed text shape", () => {
    const line = parseLogLine("ERROR connection refused");
    expect(line?.level).toBe("ERROR");
    expect(line?.message).toBe("connection refused");
  });

  it("falls back to INFO for raw text without prefix", () => {
    const line = parseLogLine("just some plain log message");
    expect(line?.level).toBe("INFO");
    expect(line?.message).toBe("just some plain log message");
  });

  it("returns null for empty lines", () => {
    expect(parseLogLine("")).toBeNull();
    expect(parseLogLine("   ")).toBeNull();
  });

  it("ignores JSON with unknown level (still tries text parse)", () => {
    const line = parseLogLine('{"level":"TRACE","msg":"x"}');
    // Falls through to "INFO" fallback because the JSON branch returned null
    expect(line?.level).toBe("INFO");
  });

  it("tolerates JSON with alternate field names (timestamp / message)", () => {
    const line = parseLogLine(
      '{"level":"INFO","timestamp":"2026-06-07","message":"hi","logger":"agentcook"}',
    );
    expect(line?.ts).toBe("2026-06-07");
    expect(line?.message).toBe("hi");
    expect(line?.module).toBe("agentcook");
  });
});

describe("log filtering · Day 31", () => {
  const lines = makeMockLogStream();

  it("respects minLevel rank", () => {
    const errOnly = lines.filter((l) => shouldShow(l, "ERROR", ""));
    expect(errOnly.every((l) => LEVEL_RANK[l.level] >= LEVEL_RANK.ERROR)).toBe(true);
    expect(errOnly.length).toBeGreaterThan(0);
  });

  it("substring search is case-insensitive", () => {
    const found = lines.filter((l) => shouldShow(l, "DEBUG", "AGENTCOOK"));
    expect(found.length).toBeGreaterThan(0);
    expect(found.every((l) => l.message.toLowerCase().includes("agentcook"))).toBe(true);
  });

  it("returns empty when search matches nothing", () => {
    expect(lines.filter((l) => shouldShow(l, "DEBUG", "nonsense-xyz-123"))).toEqual([]);
  });

  it("CRITICAL level shows for CRITICAL filter", () => {
    const crit = lines.filter((l) => shouldShow(l, "CRITICAL", ""));
    expect(crit.every((l) => l.level === "CRITICAL")).toBe(true);
  });
});
