import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useToolkits } from "@/hooks/useRuntimeData";

interface ChatPluginPickerProps {
  /** Toolkit ids sent as `plugin_ids` with the next turn. */
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  /** Toolkits the current agent already has (shown as always-on). */
  builtIn?: string[];
}

/**
 * Picks extra *toolkits* for a turn — executable tool bundles reported by
 * the runtime (`GET /api/v1/toolkits`). Unlike the plugin catalog in the
 * admin console (installable packages managed by agentcook-java), every
 * entry here can actually run right now.
 */
export default function ChatPluginPicker({ selectedIds, onChange, builtIn = [] }: ChatPluginPickerProps) {
  const { t } = useTranslation();
  const { data } = useToolkits();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const toolkits = data?.items ?? [];

  useEffect(() => {
    if (!open) return;
    function onClick(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const toggle = useCallback(
    (id: string) => {
      onChange(selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id]);
    },
    [selectedIds, onChange],
  );

  const activeCount = new Set([...builtIn, ...selectedIds]).size;

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-gray-200 px-2.5 py-1 text-xs text-gray-600 transition hover:border-gray-300 hover:bg-gray-50"
        aria-expanded={open}
        data-testid="toolkit-picker"
      >
        <span className="whitespace-nowrap">🧰 {t("plugin.selector")}</span>
        {activeCount > 0 && (
          <span className="rounded-full bg-blue-100 px-1.5 text-[10px] font-semibold text-blue-700">{activeCount}</span>
        )}
      </button>
      {open && (
        <div className="absolute bottom-full left-0 z-20 mb-2 w-80 rounded-xl border border-gray-200 bg-white p-2 shadow-lg">
          {toolkits.length === 0 && <p className="px-2 py-3 text-xs text-gray-400">{t("plugin.noPlugins")}</p>}
          {toolkits.map((kit) => {
            const always = builtIn.includes(kit.id);
            const checked = always || selectedIds.includes(kit.id);
            return (
              <label
                key={kit.id}
                className={`flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-gray-50 ${always ? "opacity-70" : ""}`}
              >
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={checked}
                  disabled={always}
                  onChange={() => toggle(kit.id)}
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-gray-800">
                    {kit.name}
                    {always && (
                      <span className="ml-1 text-[10px] font-normal text-gray-400">({t("plugin.builtIn")})</span>
                    )}
                  </span>
                  <span className="block text-xs text-gray-500">{kit.description}</span>
                  <span className="mt-0.5 block font-mono text-[10px] text-gray-400">
                    {kit.tools.map((tool) => tool.name).join(" · ")}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
