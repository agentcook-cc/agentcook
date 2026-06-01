export type LogLevel = "DEBUG" | "INFO" | "WARN" | "ERROR" | "CRITICAL";

export const LOG_LEVELS: LogLevel[] = ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"];

export const LEVEL_RANK: Record<LogLevel, number> = {
  DEBUG: 10,
  INFO: 20,
  WARN: 30,
  ERROR: 40,
  CRITICAL: 50,
};

export const LEVEL_COLOR: Record<LogLevel, string> = {
  DEBUG: "#737373", // neutral-500
  INFO: "#3b82f6", // primary-500
  WARN: "#f59e0b", // warning-500
  ERROR: "#ef4444", // danger-500
  CRITICAL: "#dc2626", // danger-600
};

export interface LogLine {
  level: LogLevel;
  message: string;
  ts: string;
  module?: string;
}

/** Parse one log line in the format `[LEVEL] [ts] [module?] message`. */
export function parseLogLine(raw: string): LogLine | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  // Try JSON shape first (structlog default): {"level":"INFO","ts":"...","msg":"..."}
  if (trimmed.startsWith("{")) {
    try {
      const j = JSON.parse(trimmed);
      const rawLevel = String(j.level ?? "INFO").toUpperCase();
      const level = (LEVEL_RANK[rawLevel as LogLevel] ? rawLevel : "INFO") as LogLevel;
      return {
        level,
        ts: j.ts ?? j.timestamp ?? new Date().toISOString(),
        message: j.msg ?? j.message ?? trimmed,
        module: j.module ?? j.logger,
      };
    } catch {
      // fall through to text parsing
    }
  }
  // Fallback: prefixed text `LEVEL message`
  const match = trimmed.match(/^(DEBUG|INFO|WARN|ERROR|CRITICAL)\s+(.*)$/);
  if (match) {
    return {
      level: match[1] as LogLevel,
      ts: new Date().toISOString(),
      message: match[2],
    };
  }
  return { level: "INFO", ts: new Date().toISOString(), message: trimmed };
}

export function shouldShow(line: LogLine, minLevel: LogLevel, search: string): boolean {
  if (LEVEL_RANK[line.level] < LEVEL_RANK[minLevel]) return false;
  if (search && !line.message.toLowerCase().includes(search.toLowerCase())) return false;
  return true;
}

/** Deterministic mock log generator for dev when Python /logs/stream is unreachable. */
export function makeMockLogStream(): LogLine[] {
  const samples: Array<[LogLevel, string]> = [
    ["INFO", "agentcook starting on :8000"],
    ["DEBUG", "loaded 8 plugins from registry"],
    ["INFO", "user alice authenticated"],
    ["WARN", "qwen-plus rate limit at 80%"],
    ["INFO", "agent loop tick=42 model=gpt-4"],
    ["ERROR", "tool web_search failed: timeout after 30s"],
    ["DEBUG", "memory compaction skipped (under threshold)"],
    ["CRITICAL", "pgvector connection lost — failover initiated"],
    ["INFO", "stream chunk delivered len=128"],
    ["WARN", "Java backend POST /api/v1/connectors returned 404"],
  ];
  const now = Date.now();
  return samples.map(([level, message], i) => ({
    level,
    message,
    ts: new Date(now - (samples.length - i) * 1500).toISOString(),
    module: "agentcook_app.main",
  }));
}
