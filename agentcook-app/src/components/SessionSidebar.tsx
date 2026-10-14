import { useTranslation } from "react-i18next";
import type { ConversationSummary } from "@/api/runtime";

interface SessionSidebarProps {
  sessions: ConversationSummary[];
  activeSessionId?: string;
  loading?: boolean;
  onSelect: (sessionId: string) => void;
  onNewChat: () => void;
  onDelete?: (session: ConversationSummary) => void;
}

function formatRelativeTime(iso: string, t: (key: string, opts?: Record<string, unknown>) => string) {
  const diff = Date.now() - Date.parse(iso);
  const minutes = Math.floor(diff / 60_000);
  if (Number.isNaN(minutes) || minutes < 1) return t("time.justNow");
  if (minutes < 60) return t("time.minutesAgo", { count: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("time.hoursAgo", { count: hours });
  return t("time.daysAgo", { count: Math.floor(hours / 24) });
}

export default function SessionSidebar({
  sessions,
  activeSessionId,
  loading = false,
  onSelect,
  onNewChat,
  onDelete,
}: SessionSidebarProps) {
  const { t } = useTranslation();
  return (
    <aside className="hidden h-full w-64 flex-col border-r border-gray-200 bg-gray-50 md:flex">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-700">{t("session.title")}</h2>
        <button
          onClick={onNewChat}
          className="rounded-lg p-1.5 text-gray-500 transition hover:bg-gray-200 hover:text-gray-700"
          title={t("chat.newChat")}
          aria-label={t("chat.newChat")}
          data-testid="new-chat"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-2" data-testid="session-list">
        {!loading && sessions.length === 0 && (
          <p className="px-3 py-6 text-center text-xs text-gray-400">{t("session.empty")}</p>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`group mb-1 flex items-center rounded-lg transition ${
              session.id === activeSessionId ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-100"
            }`}
          >
            <button onClick={() => onSelect(session.id)} className="min-w-0 flex-1 px-3 py-2 text-left">
              <p className="flex items-center gap-1.5 truncate text-sm font-medium">
                {session.active_run_id && (
                  <span
                    className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-emerald-500"
                    title={t("session.running")}
                  />
                )}
                <span className="truncate">{session.title}</span>
              </p>
              <p className="mt-0.5 text-xs text-gray-400">{formatRelativeTime(session.updated_at, t)}</p>
            </button>
            {onDelete && (
              <button
                onClick={() => onDelete(session)}
                className="mr-1 rounded p-1 text-gray-400 opacity-0 transition hover:bg-gray-200 hover:text-red-600 group-hover:opacity-100 focus:opacity-100"
                title={t("session.delete")}
                aria-label={t("session.delete")}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                >
                  <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
                </svg>
              </button>
            )}
          </div>
        ))}
      </nav>
    </aside>
  );
}
