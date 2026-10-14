/**
 * Typed client for the Python agent runtime (docs/api/v1.yaml, v2).
 *
 * Chat streaming lives in `hooks/useAgentChat.ts` (fetch + SSE); this
 * module covers the plain JSON endpoints: conversations, agents,
 * toolkits, runtime info and run cancellation.
 */
import { pythonClient } from "@/api/client";

export type ToolCallStatus = "running" | "success" | "error";

export interface ToolCallView {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: ToolCallStatus;
  output?: string | null;
  error?: string | null;
  duration_ms?: number | null;
  turn?: number | null;
}

export interface UsageView {
  input_tokens: number;
  output_tokens: number;
  cached_tokens?: number;
  total_tokens: number;
}

export interface RunMetadata {
  agent?: string;
  agent_title?: string;
  model?: string;
  provider?: string;
  usage?: UsageView;
  turns?: number;
  duration_ms?: number;
  finish_reason?: string;
  source?: string;
  warnings?: string[];
  request_id?: string;
  [key: string]: unknown;
}

export type ChatFrameType = "start" | "delta" | "tool_call" | "tool_result" | "done" | "error";

/** One SSE frame from POST /api/v1/chat/stream. */
export interface ChatFrame {
  type?: ChatFrameType;
  role?: string;
  content?: string;
  done?: boolean;
  session_id?: string;
  run_id?: string;
  tool_call?: ToolCallView;
  error?: string;
  metadata?: RunMetadata;
}

export interface ConversationSummary {
  id: string;
  title: string;
  agent: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  active_run_id?: string | null;
}

export interface TranscriptMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  tool_calls: ToolCallView[];
  metadata: RunMetadata & { error?: string };
}

export interface AgentInfo {
  name: string;
  title: string;
  description: string;
  default: boolean;
  toolkits: string[];
  skills: string[];
  memory: boolean;
  delegates: string[];
  instance_id: string;
}

export interface ToolkitInfo {
  id: string;
  name: string;
  description: string;
  tools: { name: string; description: string }[];
}

export interface RuntimeInfo {
  version: string;
  env: string;
  provider: string;
  mock_model: boolean;
  storage: string;
  auth_mode: "required" | "optional" | "disabled";
  agents: string[];
  default_agent: string;
  toolkits: string[];
  skills: number;
  active_runs: number;
}

export const runtimeApi = {
  listConversations: (limit = 50) =>
    pythonClient.get<{ items: ConversationSummary[]; total: number }>(`/api/v1/conversations?limit=${limit}`),
  getConversation: (sessionId: string) =>
    pythonClient.get<{ session: ConversationSummary; messages: TranscriptMessage[] }>(
      `/api/v1/conversations/${encodeURIComponent(sessionId)}`,
    ),
  renameConversation: (sessionId: string, title: string) =>
    pythonClient.raw.patch<ConversationSummary>(`/api/v1/conversations/${encodeURIComponent(sessionId)}`, { title }),
  deleteConversation: (sessionId: string) =>
    pythonClient.del<void>(`/api/v1/conversations/${encodeURIComponent(sessionId)}`),
  listAgents: () => pythonClient.get<{ items: AgentInfo[]; default_agent: string }>("/api/v1/agents"),
  listToolkits: () => pythonClient.get<{ items: ToolkitInfo[] }>("/api/v1/toolkits"),
  getRuntime: () => pythonClient.get<RuntimeInfo>("/api/v1/runtime"),
  cancelRun: (runId: string) =>
    pythonClient.post<{ run_id: string; cancelled: boolean }>(`/api/v1/chat/runs/${encodeURIComponent(runId)}/cancel`),
};

/** Client-side conversation id; the runtime creates it on first message. */
export function newSessionId(): string {
  return `c-${crypto.randomUUID()}`;
}
