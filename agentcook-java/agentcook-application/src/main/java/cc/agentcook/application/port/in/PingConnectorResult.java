package cc.agentcook.application.port.in;

import cc.agentcook.domain.connector.ConnectorStatus;

/**
 * Result of a ping operation. Day 29 returns mock latency since the
 * real upstream IM check lives in Phase 4 (DingTalk / Feishu / Telegram
 * SDK integration).
 */
public record PingConnectorResult(ConnectorStatus status, long latencyMs) {
}
