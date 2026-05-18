import { useCallback } from "react";

export interface SessionItem {
  id: string;
  title: string;
  updatedAt: number;
}

interface SessionSidebarProps {
  sessions: SessionItem[];
  activeSessionId?: string;
  onSelect: (sessionId: string) => void;
  onNewChat: () => void;
}

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNewChat,
}: SessionSidebarProps) {
  const handleSelect = useCallback(
    (sessionId: string) => {
      onSelect(sessionId);
    },
    [onSelect],
  );

  return (
    <aside className="flex h-full w-64 flex-col border-r border-gray-200 bg-gray-50">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-700">Conversations</h2>
        <button
          onClick={onNewChat}
          className="rounded-lg p-1.5 text-gray-500 transition hover:bg-gray-200 hover:text-gray-700"
          title="New chat"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 && (
          <p className="px-3 py-6 text-center text-xs text-gray-400">
            No conversations yet
          </p>
        )}
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => handleSelect(session.id)}
            className={`mb-1 w-full rounded-lg px-3 py-2 text-left transition ${
              session.id === activeSessionId
                ? "bg-blue-50 text-blue-700"
                : "text-gray-700 hover:bg-gray-100"
            }`}
          >
            <p className="truncate text-sm font-medium">{session.title}</p>
            <p className="mt-0.5 text-xs text-gray-400">
              {formatRelativeTime(session.updatedAt)}
            </p>
          </button>
        ))}
      </nav>
    </aside>
  );
}
