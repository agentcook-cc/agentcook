import { ref, onScopeDispose } from "vue";
import { useAuthStore } from "@/stores/auth";

/**
 * Day 28 — Vue 3 composable for consuming server-sent event streams.
 *
 * Mirrors `agentcook-app/src/hooks/useSseChat.ts` (React) so the SSE wire
 * format stays identical across surfaces. Differences from the React hook:
 *   - URL + body are caller-supplied (this is generic, the React one is hard
 *     wired to /api/v1/agent/chat)
 *   - reactive `chunks` / `running` / `error` refs make template binding easy
 *   - heartbeat uses 30s default (admin Skill test is shorter than chat)
 */

export interface SseStreamOptions {
  url: string;
  body?: unknown;
  maxRetries?: number;
  heartbeatMs?: number;
}

interface ParseResult {
  content: string;
  done: boolean;
  remainder: string;
}

export function parseSseLines(raw: string): ParseResult {
  const lastNewline = raw.lastIndexOf("\n");
  if (lastNewline === -1) return { content: "", done: false, remainder: raw };

  const complete = raw.slice(0, lastNewline + 1);
  const remainder = raw.slice(lastNewline + 1);
  const lines = complete.split("\n");
  let content = "";
  let done = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith(":")) continue;
    if (trimmed.startsWith("data: ")) {
      const payload = trimmed.slice(6);
      if (payload === "[DONE]") {
        done = true;
        break;
      }
      try {
        const parsed = JSON.parse(payload);
        content += parsed.content ?? parsed.delta ?? parsed.text ?? "";
      } catch {
        content += payload;
      }
    }
  }
  return { content, done, remainder };
}

const BASE_DELAY_MS = 500;
const MAX_DELAY_MS = 8_000;

function computeBackoff(attempt: number): number {
  const delay = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
  const jitter = delay * 0.2 * Math.random();
  return delay + jitter;
}

export function useSseStream() {
  const accumulated = ref("");
  const running = ref(false);
  const error = ref<string | null>(null);
  let abortController: AbortController | null = null;
  let heartbeatTimer: ReturnType<typeof setTimeout> | null = null;

  function clearHeartbeat() {
    if (heartbeatTimer) {
      clearTimeout(heartbeatTimer);
      heartbeatTimer = null;
    }
  }

  function resetHeartbeat(ms: number, onTimeout: () => void) {
    clearHeartbeat();
    heartbeatTimer = setTimeout(onTimeout, ms);
  }

  async function start(opts: SseStreamOptions): Promise<void> {
    cancel();
    accumulated.value = "";
    error.value = null;
    running.value = true;

    const { url, body, maxRetries = 2, heartbeatMs = 30_000 } = opts;
    const controller = new AbortController();
    abortController = controller;

    let attempt = 0;
    while (attempt <= maxRetries) {
      try {
        const token = useAuthStore().accessToken;
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          if (attempt < maxRetries && response.status >= 500) {
            const delay = computeBackoff(attempt);
            attempt++;
            await new Promise((r) => setTimeout(r, delay));
            continue;
          }
          error.value = `Server returned ${response.status}`;
          running.value = false;
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let rawBuffer = "";
        let heartbeatTimedOut = false;

        resetHeartbeat(heartbeatMs, () => {
          heartbeatTimedOut = true;
          reader.cancel().catch(() => undefined);
        });

        while (true) {
          const { done: streamDone, value } = await reader.read();

          if (heartbeatTimedOut) {
            error.value = "Heartbeat timeout — server stopped sending data";
            clearHeartbeat();
            running.value = false;
            return;
          }

          if (streamDone) {
            clearHeartbeat();
            running.value = false;
            return;
          }

          resetHeartbeat(heartbeatMs, () => {
            heartbeatTimedOut = true;
            reader.cancel().catch(() => undefined);
          });

          rawBuffer += decoder.decode(value, { stream: true });
          const parsed = parseSseLines(rawBuffer);
          rawBuffer = parsed.remainder;

          if (parsed.content) {
            accumulated.value += parsed.content;
          }

          if (parsed.done) {
            clearHeartbeat();
            running.value = false;
            return;
          }
        }
      } catch (err) {
        clearHeartbeat();
        if (controller.signal.aborted) {
          running.value = false;
          return;
        }
        if (attempt < maxRetries) {
          attempt++;
          const delay = computeBackoff(attempt);
          await new Promise((r) => setTimeout(r, delay));
          continue;
        }
        error.value = err instanceof Error ? err.message : "Network error";
        running.value = false;
        return;
      }
    }
    error.value = `Failed after ${maxRetries + 1} attempts`;
    running.value = false;
  }

  function cancel() {
    clearHeartbeat();
    abortController?.abort();
    abortController = null;
    running.value = false;
  }

  function reset() {
    cancel();
    accumulated.value = "";
    error.value = null;
  }

  onScopeDispose(() => cancel());

  return { accumulated, running, error, start, cancel, reset };
}
