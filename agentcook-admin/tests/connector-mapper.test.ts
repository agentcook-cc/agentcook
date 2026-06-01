import { describe, it, expect } from "vitest";
import { fromJavaDto, PROVIDER_META } from "@/views/connectors/connectorTypes";

describe("connector fromJavaDto mapper · Day 29", () => {
  it("uses provider/displayName when D enriches the schema", () => {
    const row = fromJavaDto({
      id: "c1",
      status: "CONNECTED",
      // Fields D has not yet declared but will once schema is enriched:
      provider: "feishu",
      displayName: "Feishu · Engineering",
      lastConnectedAt: "2026-06-05T10:00:00Z",
    } as unknown as Parameters<typeof fromJavaDto>[0]);

    expect(row.id).toBe("c1");
    expect(row.provider).toBe("feishu");
    expect(row.displayName).toBe("Feishu · Engineering");
    expect(row.status).toBe("CONNECTED");
    expect(row.lastConnectedAt).toBe("2026-06-05T10:00:00Z");
  });

  it("falls back to provider label when displayName missing", () => {
    const row = fromJavaDto({
      id: "c2",
      status: "DISCONNECTED",
      provider: "telegram",
    } as unknown as Parameters<typeof fromJavaDto>[0]);
    expect(row.displayName).toBe(PROVIDER_META.telegram.label);
  });

  it("defaults provider to dingtalk when D's minimal schema omits it", () => {
    const row = fromJavaDto({
      id: "c3",
      pluginId: "p-9",
      status: "CONNECTED",
    });
    expect(row.provider).toBe("dingtalk");
    expect(row.pluginId).toBe("p-9");
    expect(row.status).toBe("CONNECTED");
  });

  it("supports snake_case alternates (last_connected_at / display_name)", () => {
    const row = fromJavaDto({
      id: "c4",
      status: "ERROR",
      provider: "slack",
      display_name: "Slack · Support",
      last_connected_at: "2026-06-04T22:00:00Z",
    } as unknown as Parameters<typeof fromJavaDto>[0]);
    expect(row.displayName).toBe("Slack · Support");
    expect(row.lastConnectedAt).toBe("2026-06-04T22:00:00Z");
  });

  it("defaults status to DISCONNECTED when missing", () => {
    const row = fromJavaDto({ id: "c5" } as unknown as Parameters<typeof fromJavaDto>[0]);
    expect(row.status).toBe("DISCONNECTED");
  });
});
