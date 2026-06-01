import { useRef, useCallback } from "react";
import { useAuthStore } from "@/stores/auth";

interface SseChatOptions {
  onChunk: (accumulated: string) => void;
  onDone: (finalContent: string) => void;
  onError: (errorMessage: string) => void;
  maxRetries?: number;
  /** SSE endpoint URL. Defaults to Python backend's /api/v1/chat/stream */
  endpoint?: string;
  /** Additional body fields merged into the request (e.g. session_id, plugins) */
  extraBody?: Record<string, unknown>;
}

const PYTHON_BASE =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_PYTHON_API_BASE_URL) ||
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://localhost:8000";

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30_000;
const HEARTBEAT_TIMEOUT_MS = 45_000;

function computeBackoffDelay(attempt: number): number {
  const delay = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
  const jitter = delay * 0.2 * Math.random();
  return delay + jitter;
}

function parseSseLines(raw: string): { content: string; done: boolean; remainder: string } {
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

export function useSseChat({
  onChunk,
  onDone,
  onError,
  maxRetries = 3,
  endpoint = "/api/v1/chat/stream",
  extraBody = {},
}: SseChatOptions) {
  const abortRef = useRef<AbortController | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearHeartbeat() {
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }

  function resetHeartbeat(onTimeout: () => void) {
    clearHeartbeat();
    heartbeatTimerRef.current = setTimeout(onTimeout, HEARTBEAT_TIMEOUT_MS);
  }

  const send = useCallback(async (message: string): Promise<void> => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    let attempt = 0;
    let accumulated = "";

    while (attempt <= maxRetries) {
      try {
        const token = useAuthStore.getState().accessToken;
        const url = endpoint.startsWith("http") ? endpoint : `${PYTHON_BASE}${endpoint}`;
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ message, ...extraBody }),
          signal: controller.signal,
        });

        if (response.status === 401) {
          const refreshed = await useAuthStore.getState().refreshAccessToken();
          if (!refreshed) {
            onError("Session expired. Please sign in again.");
            return;
          }
          continue;
        }

        if (!response.ok || !response.body) {
          if (attempt < maxRetries && response.status >= 500) {
            const delay = computeBackoffDelay(attempt);
            attempt++;
            await new Promise((resolve) => setTimeout(resolve, delay));
            continue;
          }
          onError(`Server returned ${response.status}.`);
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let rawBuffer = "";
        let heartbeatTimedOut = false;

        resetHeartbeat(() => {
          heartbeatTimedOut = true;
          reader.cancel();
        });

        while (true) {
          const { done: streamDone, value } = await reader.read();

          if (heartbeatTimedOut) {
            if (attempt < maxRetries) {
              attempt++;
              const delay = computeBackoffDelay(attempt);
              await new Promise((resolve) => setTimeout(resolve, delay));
              break;
            }
            onError("Connection lost — server stopped responding.");
            clearHeartbeat();
            return;
          }

          if (streamDone) {
            clearHeartbeat();
            if (!accumulated) {
              onError("No response received.");
            } else {
              onDone(accumulated);
            }
            return;
          }

          resetHeartbeat(() => {
            heartbeatTimedOut = true;
            reader.cancel();
          });

          rawBuffer += decoder.decode(value, { stream: true });
          const { content, done: sseDone, remainder } = parseSseLines(rawBuffer);
          rawBuffer = remainder;

          if (content) {
            accumulated += content;
            onChunk(accumulated);
          }

          if (sseDone) {
            clearHeartbeat();
            onDone(accumulated);
            return;
          }
        }
      } catch (error) {
        clearHeartbeat();
        if (controller.signal.aborted) return;

        if (attempt < maxRetries) {
          const delay = computeBackoffDelay(attempt);
          attempt++;
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }

        const errorText = error instanceof Error ? error.message : "Network error";
        onError(errorText);
        return;
      }
    }

    onError(`Failed after ${maxRetries + 1} attempts.`);
  }, [onChunk, onDone, onError, maxRetries]);

  const cancel = useCallback(() => {
    clearHeartbeat();
    abortRef.current?.abort();
  }, []);

  return { send, cancel };
}
