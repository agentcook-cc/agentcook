import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ToolCallView } from "@/api/runtime";

const STATUS_STYLE: Record<ToolCallView["status"], { border: string; badge: string; icon: string }> = {
  running: { border: "border-amber-200", badge: "bg-amber-50 text-amber-700", icon: "" },
  success: { border: "border-emerald-200", badge: "bg-emerald-50 text-emerald-700", icon: "✓" },
  error: { border: "border-red-300", badge: "bg-red-50 text-red-700", icon: "✕" },
};

function formatDuration(ms?: number | null): string {
  if (ms == null) return "";
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function prettyOutput(output: string): string {
  try {
    return JSON.stringify(JSON.parse(output), null, 2);
  } catch {
    return output;
  }
}

/** Human label for a tool call: delegations and skill loads read as actions. */
export function useToolLabel(call: ToolCallView): string {
  const { t } = useTranslation();
  if (call.name.startsWith("delegate_to_")) {
    return t("tool.delegate", { agent: call.name.slice("delegate_to_".length) });
  }
  if (call.name === "load_skill" && typeof call.arguments.skill === "string") {
    return t("tool.loadSkill", { skill: call.arguments.skill });
  }
  return call.name;
}

export default function ToolCallCard({ call }: { call: ToolCallView }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const style = STATUS_STYLE[call.status];
  const label = useToolLabel(call);

  return (
    <div
      className={`my-1.5 rounded-lg border bg-white text-xs shadow-sm ${style.border}`}
      data-testid="tool-call"
      data-tool={call.name}
      data-status={call.status}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left"
      >
        <span className={`flex h-5 w-5 items-center justify-center rounded-full ${style.badge}`}>
          {call.status === "running" ? (
            <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
          ) : (
            style.icon
          )}
        </span>
        <span className="font-medium text-gray-800">🔧 {label}</span>
        <span className={`rounded px-1.5 py-0.5 ${style.badge}`}>{t(`tool.status.${call.status}`)}</span>
        <span className="ml-auto text-gray-400">{formatDuration(call.duration_ms)}</span>
        <span className="text-gray-400" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-gray-100 px-3 py-2">
          <section>
            <div className="mb-1 font-semibold uppercase tracking-wide text-gray-500">{t("tool.input")}</div>
            <pre className="max-h-48 overflow-auto rounded bg-gray-50 p-2 font-mono text-[11px] text-gray-800">
              {prettyJson(call.arguments)}
            </pre>
          </section>
          {call.status !== "running" && (
            <section>
              <div
                className={`mb-1 font-semibold uppercase tracking-wide ${call.status === "error" ? "text-red-600" : "text-gray-500"}`}
              >
                {call.status === "error" ? t("tool.error") : t("tool.output")}
              </div>
              <pre
                className={`max-h-64 overflow-auto whitespace-pre-wrap rounded p-2 font-mono text-[11px] ${call.status === "error" ? "bg-red-50 text-red-800" : "bg-gray-50 text-gray-800"}`}
              >
                {call.status === "error" ? (call.error ?? call.output) : prettyOutput(call.output ?? "")}
              </pre>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
