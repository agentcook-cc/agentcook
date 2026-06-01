import { useEffect, useRef, useState } from "react";

export type PluginActivationStatus = "ACTIVE" | "INACTIVE";

export interface PluginItem {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: PluginActivationStatus;
}

interface PluginSelectorProps {
  plugins: PluginItem[];
  selectedId?: string;
  onSelect: (id: string) => void;
  placeholder?: string;
}

const STATUS_BADGE: Record<PluginActivationStatus, string> = {
  ACTIVE: "bg-green-100 text-green-700",
  INACTIVE: "bg-gray-100 text-gray-500",
};

export default function PluginSelector({
  plugins,
  selectedId,
  onSelect,
  placeholder = "Select a plugin",
}: PluginSelectorProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  const selected = plugins.find((p) => p.id === selectedId);

  return (
    <div ref={rootRef} className="relative inline-block w-72 text-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-left transition hover:border-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selected ? (
          <>
            <span className="text-lg" aria-hidden>
              {selected.icon}
            </span>
            <span className="flex-1 truncate font-medium text-gray-900">
              {selected.name}
            </span>
            <span
              className={`rounded px-1.5 py-0.5 text-xs ${STATUS_BADGE[selected.status]}`}
            >
              {selected.status}
            </span>
          </>
        ) : (
          <span className="flex-1 text-gray-400">{placeholder}</span>
        )}
        <span className="text-gray-400" aria-hidden>
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute z-10 mt-1 max-h-80 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
        >
          {plugins.length === 0 && (
            <li className="px-3 py-4 text-center text-xs text-gray-500">
              No plugins available
            </li>
          )}
          {plugins.map((plugin) => {
            const isSelected = plugin.id === selectedId;
            const isDisabled = plugin.status === "INACTIVE";
            return (
              <li
                key={plugin.id}
                role="option"
                aria-selected={isSelected}
                aria-disabled={isDisabled}
                onClick={() => {
                  if (isDisabled) return;
                  onSelect(plugin.id);
                  setOpen(false);
                }}
                className={`flex cursor-pointer items-start gap-3 px-3 py-2 transition ${
                  isDisabled
                    ? "cursor-not-allowed opacity-50"
                    : "hover:bg-gray-50"
                } ${isSelected ? "bg-blue-50" : ""}`}
              >
                <span className="mt-0.5 text-xl" aria-hidden>
                  {plugin.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium text-gray-900">
                      {plugin.name}
                    </span>
                    <span
                      className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${STATUS_BADGE[plugin.status]}`}
                    >
                      {plugin.status}
                    </span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-xs text-gray-500">
                    {plugin.description}
                  </p>
                </div>
                {isSelected && (
                  <span className="mt-1 text-blue-600" aria-hidden>
                    ✓
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export const MOCK_PLUGINS: PluginItem[] = [
  {
    id: "github-connector",
    name: "GitHub Connector",
    description: "Read/write issues, PRs, and repo files via GitHub REST API.",
    icon: "🐙",
    status: "ACTIVE",
  },
  {
    id: "slack-integration",
    name: "Slack Integration",
    description: "Post messages and react to events from Slack workspaces.",
    icon: "💬",
    status: "ACTIVE",
  },
  {
    id: "mcp-server",
    name: "Model Context Protocol",
    description: "Generic MCP-compatible tool server with stdio transport.",
    icon: "🔌",
    status: "ACTIVE",
  },
  {
    id: "web-search",
    name: "Web Search",
    description: "Search the public web and return cited snippets.",
    icon: "🔍",
    status: "ACTIVE",
  },
  {
    id: "legacy-bridge",
    name: "Legacy API Bridge",
    description: "Adapter for deprecated v0 endpoints. Will be removed soon.",
    icon: "🪝",
    status: "INACTIVE",
  },
];
