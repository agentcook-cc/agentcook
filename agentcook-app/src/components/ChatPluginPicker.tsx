import { useState, useEffect, useCallback, useRef } from "react";
import { javaClient } from "@/api/client";

interface PluginDto {
  id: string;
  name: string;
  kind: string;
  status: string;
}

interface ChatPluginPickerProps {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}

const MOCK_PLUGINS: PluginDto[] = [
  { id: "p1", name: "Code Interpreter", kind: "MCP", status: "PUBLISHED" },
  { id: "p2", name: "GitHub Connector", kind: "OAUTH", status: "PUBLISHED" },
  { id: "p3", name: "Web Search", kind: "HTTP", status: "PUBLISHED" },
];

export default function ChatPluginPicker({ selectedIds, onChange }: ChatPluginPickerProps) {
  const [plugins, setPlugins] = useState<PluginDto[]>([]);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await javaClient.get<PluginDto[]>("/api/v1/plugins");
        setPlugins(data.filter((p) => p.status === "PUBLISHED"));
      } catch {
        setPlugins(MOCK_PLUGINS);
      }
    }
    load();
  }, []);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const toggle = useCallback(
    (id: string) => {
      const next = selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id];
      onChange(next);
    },
    [selectedIds, onChange],
  );

  return (
    <div ref={rootRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition hover:border-blue-400 hover:text-blue-600"
        type="button"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
        Plugins{selectedIds.length > 0 && ` (${selectedIds.length})`}
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-20 mb-2 w-60 rounded-lg border border-gray-200 bg-white p-2 shadow-lg">
          <p className="mb-1.5 px-2 text-xs font-medium text-gray-500">Select tools for this chat</p>
          {plugins.length === 0 && (
            <p className="px-2 py-3 text-center text-xs text-gray-400">No plugins available</p>
          )}
          {plugins.map((plugin) => (
            <label
              key={plugin.id}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 transition hover:bg-gray-50"
            >
              <input
                type="checkbox"
                checked={selectedIds.includes(plugin.id)}
                onChange={() => toggle(plugin.id)}
                className="h-3.5 w-3.5 rounded border-gray-300 text-blue-600"
              />
              <span className="flex-1 truncate text-sm text-gray-700">{plugin.name}</span>
              <span className="shrink-0 text-[10px] text-gray-400">{plugin.kind}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
