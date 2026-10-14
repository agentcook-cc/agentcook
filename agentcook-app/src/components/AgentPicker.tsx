import { useTranslation } from "react-i18next";
import type { AgentInfo } from "@/api/runtime";

interface AgentPickerProps {
  agents: AgentInfo[];
  value?: string;
  onChange: (agent: string) => void;
  disabled?: boolean;
}

/** Choose which agent answers in this conversation. */
export default function AgentPicker({ agents, value, onChange, disabled }: AgentPickerProps) {
  const { t } = useTranslation();
  if (agents.length <= 1) return null;
  const current = agents.find((a) => a.name === value) ?? agents[0];
  return (
    <label className="flex items-center gap-2 text-xs text-gray-500">
      <span className="hidden sm:inline">{t("agent.label")}</span>
      <select
        value={current.name}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        title={current.description}
        data-testid="agent-picker"
        className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-gray-800 outline-none focus:border-blue-500 disabled:opacity-60"
      >
        {agents.map((agent) => (
          <option key={agent.name} value={agent.name}>
            {agent.title}
          </option>
        ))}
      </select>
    </label>
  );
}
