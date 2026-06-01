import type { components } from "@/api/types.java.gen";

/**
 * Day 29 — D's java-v1.yaml only declares minimal ConnectorResponse
 * (`id, pluginId, status`) carried over from activate-plugin. The Connector
 * list/CRUD UI needs more (provider, displayName, last_connected_at, config
 * shape) — flag in progress and extend locally until D enriches the schema.
 */
export type JavaConnectorResponseDto = components["schemas"]["ConnectorResponse"];

export type ConnectorProvider =
  | "dingtalk"
  | "feishu"
  | "telegram"
  | "discord"
  | "slack";

export type ConnectorStatus = "CONNECTED" | "DISCONNECTED" | "ERROR";

/** Display row consumed by ConnectorListView — superset of JavaConnectorResponseDto. */
export interface ConnectorRow {
  id: string;
  pluginId?: string;
  provider: ConnectorProvider;
  displayName: string;
  status: ConnectorStatus;
  lastConnectedAt?: string;
  config?: Record<string, unknown>;
}

export const PROVIDER_META: Record<
  ConnectorProvider,
  { label: string; icon: string; brandColor: string }
> = {
  dingtalk: { label: "DingTalk", icon: "💬", brandColor: "#1677ff" },
  feishu: { label: "Feishu / Lark", icon: "📨", brandColor: "#3370ff" },
  telegram: { label: "Telegram", icon: "✈️", brandColor: "#26a5e4" },
  discord: { label: "Discord", icon: "🎮", brandColor: "#5865f2" },
  slack: { label: "Slack", icon: "💼", brandColor: "#4a154b" },
};

export const PROVIDERS: ConnectorProvider[] = [
  "dingtalk",
  "feishu",
  "telegram",
  "discord",
  "slack",
];

/**
 * Map a raw Java ConnectorResponse into the row shape. Until D enriches the
 * schema we fall back to placeholder values; replace the heuristics here once
 * D ships provider + display_name + last_connected_at.
 */
export function fromJavaDto(dto: JavaConnectorResponseDto): ConnectorRow {
  const raw = dto as JavaConnectorResponseDto & {
    provider?: string;
    displayName?: string;
    display_name?: string;
    lastConnectedAt?: string;
    last_connected_at?: string;
    config?: Record<string, unknown>;
  };
  const provider = (raw.provider ?? "dingtalk") as ConnectorProvider;
  const status = (dto.status ?? "DISCONNECTED") as ConnectorStatus;
  return {
    id: String(dto.id ?? crypto.randomUUID()),
    pluginId: dto.pluginId,
    provider,
    displayName:
      raw.displayName ?? raw.display_name ?? PROVIDER_META[provider]?.label ?? provider,
    status,
    lastConnectedAt: raw.lastConnectedAt ?? raw.last_connected_at,
    config: raw.config,
  };
}
