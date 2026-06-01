import { useState } from "react";

export type SkillCallStatus = "pending" | "success" | "error";

export interface SkillCall {
  id: string;
  name: string;
  status: SkillCallStatus;
  input: Record<string, unknown>;
  output?: unknown;
  error?: string;
  durationMs?: number;
  startedAt: number;
}

interface SkillCallCardProps {
  call: SkillCall;
  defaultExpanded?: boolean;
}

const STATUS_META: Record<
  SkillCallStatus,
  { label: string; icon: string; border: string; badge: string }
> = {
  pending: {
    label: "Running",
    icon: "⏳",
    border: "border-gray-300",
    badge: "bg-gray-100 text-gray-700",
  },
  success: {
    label: "Success",
    icon: "✓",
    border: "border-green-200",
    badge: "bg-green-100 text-green-700",
  },
  error: {
    label: "Failed",
    icon: "✕",
    border: "border-red-400",
    badge: "bg-red-100 text-red-700",
  },
};

function formatDuration(ms?: number): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function SkillCallCard({
  call,
  defaultExpanded = false,
}: SkillCallCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const meta = STATUS_META[call.status];

  return (
    <div
      className={`my-2 rounded-lg border-2 bg-white shadow-sm transition ${meta.border}`}
      data-status={call.status}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left"
        aria-expanded={expanded}
      >
        <span
          className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${meta.badge}`}
          aria-hidden
        >
          {call.status === "pending" ? (
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
          ) : (
            meta.icon
          )}
        </span>
        <span className="flex-1 truncate text-sm font-medium text-gray-900">
          {call.name}
        </span>
        <span className={`rounded px-1.5 py-0.5 text-xs ${meta.badge}`}>
          {meta.label}
        </span>
        <span className="text-xs text-gray-500" title="Duration">
          {formatDuration(call.durationMs)}
        </span>
        <span className="text-gray-400" aria-hidden>
          {expanded ? "▾" : "▸"}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-gray-100 px-3 py-2 text-xs">
          <section className="mb-2">
            <div className="mb-1 font-semibold uppercase tracking-wide text-gray-500">
              Input
            </div>
            <pre className="overflow-x-auto rounded bg-gray-50 p-2 font-mono text-[11px] leading-relaxed text-gray-800">
              {formatJson(call.input)}
            </pre>
          </section>

          {call.status === "success" && call.output !== undefined && (
            <section>
              <div className="mb-1 font-semibold uppercase tracking-wide text-gray-500">
                Output
              </div>
              <pre className="overflow-x-auto rounded bg-gray-50 p-2 font-mono text-[11px] leading-relaxed text-gray-800">
                {formatJson(call.output)}
              </pre>
            </section>
          )}

          {call.status === "error" && (
            <section>
              <div className="mb-1 font-semibold uppercase tracking-wide text-red-600">
                Error
              </div>
              <pre className="overflow-x-auto rounded bg-red-50 p-2 font-mono text-[11px] leading-relaxed text-red-800">
                {call.error ?? "(no error message)"}
              </pre>
            </section>
          )}

          {call.status === "pending" && (
            <div className="text-[11px] italic text-gray-500">
              Waiting for tool response…
            </div>
          )}
        </div>
      )}
    </div>
  );
}
