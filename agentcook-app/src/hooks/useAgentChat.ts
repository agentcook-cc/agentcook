import { useCallback, useReducer, useRef } from "react";
import { runtimeApi, type ChatFrame, type RunMetadata, type ToolCallView, type TranscriptMessage } from "@/api/runtime";
import { readSseJson } from "@/lib/sse";
import { useAuthStore } from "@/stores/auth";

/**
 * Chat state + transport for the agent runtime.
 *
 * - Streams `POST /api/v1/chat/stream` frames into one assistant bubble
 *   per turn: text deltas append to `content`, tool frames upsert into
 *   `toolCalls` (so a card flips from "running" to "success" in place).
 * - `stop()` cancels the run server-side (the run would otherwise keep
 *   going — runs outlive the HTTP connection by design) and aborts the
 *   local stream.
 * - Never auto-retries a POST that may have started a run: a duplicate
 *   turn would double-bill and double-write the transcript. A 401 before
 *   streaming starts is retried once after a token refresh, since the
 *   server provably did nothing.
 */

export type MessageStatus = "streaming" | "done" | "error" | "cancelled";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  toolCalls: ToolCallView[];
  status: MessageStatus;
  error?: string;
  meta?: RunMetadata;
}

interface State {
  messages: ChatMessage[];
  runId: string | null;
  streaming: boolean;
}

type Action =
  | { type: "reset"; messages: ChatMessage[] }
  | { type: "start"; user: ChatMessage; assistant: ChatMessage }
  | { type: "frame"; id: string; frame: ChatFrame }
  | { type: "fail"; id: string; error: string }
  | { type: "settle"; id: string };

function upsertTool(calls: ToolCallView[], call: ToolCallView): ToolCallView[] {
  const index = calls.findIndex((c) => c.id === call.id);
  if (index === -1) return [...calls, call];
  const next = calls.slice();
  next[index] = { ...next[index], ...call };
  return next;
}

function applyFrame(message: ChatMessage, frame: ChatFrame): ChatMessage {
  switch (frame.type) {
    case "start":
      return { ...message, meta: { ...message.meta, ...frame.metadata } };
    case "tool_call":
    case "tool_result":
      return frame.tool_call ? { ...message, toolCalls: upsertTool(message.toolCalls, frame.tool_call) } : message;
    case "done": {
      const cancelled = frame.metadata?.finish_reason === "cancelled";
      return {
        ...message,
        status: cancelled ? "cancelled" : "done",
        meta: { ...message.meta, ...frame.metadata },
      };
    }
    case "error":
      return {
        ...message,
        status: "error",
        error: frame.error ?? "The agent run failed.",
        meta: { ...message.meta, ...frame.metadata },
      };
    case "delta":
    default:
      // v1 frames have no `type`; treat any content as a text delta.
      return frame.content ? { ...message, content: message.content + frame.content } : message;
  }
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "reset":
      return { messages: action.messages, runId: null, streaming: false };
    case "start":
      return {
        messages: [...state.messages, action.user, action.assistant],
        runId: null,
        streaming: true,
      };
    case "frame": {
      const runId = action.frame.type === "start" ? (action.frame.run_id ?? null) : state.runId;
      return {
        ...state,
        runId,
        messages: state.messages.map((m) => (m.id === action.id ? applyFrame(m, action.frame) : m)),
      };
    }
    case "fail":
      return {
        ...state,
        streaming: false,
        runId: null,
        messages: state.messages.map((m) => (m.id === action.id ? { ...m, status: "error", error: action.error } : m)),
      };
    case "settle":
      return {
        ...state,
        streaming: false,
        runId: null,
        messages: state.messages.map((m) =>
          m.id === action.id && m.status === "streaming" ? { ...m, status: "done" } : m,
        ),
      };
  }
}

const PYTHON_BASE =
  (typeof import.meta !== "undefined" &&
    (import.meta.env?.VITE_PYTHON_API_BASE_URL || import.meta.env?.VITE_API_BASE_URL)) ||
  "";

export function transcriptToMessages(messages: TranscriptMessage[]): ChatMessage[] {
  return messages.map((m) => {
    const finish = m.metadata?.finish_reason;
    const status: MessageStatus = m.metadata?.error ? "error" : finish === "cancelled" ? "cancelled" : "done";
    return {
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: m.created_at ? Date.parse(m.created_at) : Date.now(),
      toolCalls: m.tool_calls ?? [],
      status,
      error: m.metadata?.error,
      meta: m.metadata,
    };
  });
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (body && typeof body.message === "string") return body.message;
  } catch {
    // fall through
  }
  return `Server returned ${response.status}.`;
}

export interface SendOptions {
  sessionId: string;
  text: string;
  agent?: string;
  pluginIds?: string[];
  headers?: Record<string, string>;
}

export function useAgentChat(options: { onTurnFinished?: () => void } = {}) {
  const [state, dispatch] = useReducer(reducer, { messages: [], runId: null, streaming: false });
  const abortRef = useRef<AbortController | null>(null);
  const runIdRef = useRef<string | null>(null);
  runIdRef.current = state.runId;
  const onFinishedRef = useRef(options.onTurnFinished);
  onFinishedRef.current = options.onTurnFinished;

  const reset = useCallback((messages: ChatMessage[] = []) => {
    abortRef.current?.abort();
    dispatch({ type: "reset", messages });
  }, []);

  const send = useCallback(async ({ sessionId, text, agent, pluginIds, headers }: SendOptions) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const now = Date.now();
    const assistantId = crypto.randomUUID();
    dispatch({
      type: "start",
      user: {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        createdAt: now,
        toolCalls: [],
        status: "done",
      },
      assistant: {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: now,
        toolCalls: [],
        status: "streaming",
      },
    });

    const body = JSON.stringify({
      session_id: sessionId,
      message: text,
      ...(agent ? { agent } : {}),
      ...(pluginIds && pluginIds.length ? { plugin_ids: pluginIds } : {}),
    });

    const post = () => {
      const token = useAuthStore.getState().accessToken;
      return fetch(`${PYTHON_BASE}/api/v1/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...headers,
        },
        body,
        signal: controller.signal,
      });
    };

    try {
      let response = await post();
      if (response.status === 401 && useAuthStore.getState().refreshToken) {
        if (await useAuthStore.getState().refreshAccessToken()) response = await post();
      }
      if (!response.ok || !response.body) {
        dispatch({ type: "fail", id: assistantId, error: await errorMessage(response) });
        return;
      }
      let terminal = false;
      for await (const frame of readSseJson<ChatFrame>(response.body, controller.signal)) {
        dispatch({ type: "frame", id: assistantId, frame });
        if (frame.done) terminal = true;
      }
      if (!terminal && !controller.signal.aborted) {
        dispatch({
          type: "fail",
          id: assistantId,
          error: "Connection closed before the reply finished. Reload the conversation to see the saved result.",
        });
        return;
      }
      dispatch({ type: "settle", id: assistantId });
    } catch (error) {
      if (controller.signal.aborted) {
        dispatch({ type: "settle", id: assistantId });
        return;
      }
      dispatch({
        type: "fail",
        id: assistantId,
        error: error instanceof Error ? error.message : "Network error",
      });
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      onFinishedRef.current?.();
    }
  }, []);

  const stop = useCallback(async () => {
    const runId = runIdRef.current;
    if (runId) {
      try {
        // Server-side cancel persists the partial answer and sends a final
        // "cancelled" frame, which settles the bubble.
        await runtimeApi.cancelRun(runId);
        return;
      } catch {
        // Run already finished or unreachable — fall back to a local abort.
      }
    }
    abortRef.current?.abort();
  }, []);

  return {
    messages: state.messages,
    streaming: state.streaming,
    runId: state.runId,
    send,
    stop,
    reset,
  };
}
