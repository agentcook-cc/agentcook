package cc.agentcook.domain.plugin;

/**
 * Plugin transport/integration kind.
 * Aligned with Agent A's ConnectorKind (Day 17 connector.py).
 */
public enum PluginKind {
    MCP,
    HTTP,
    OAUTH,
    WEBHOOK
}
