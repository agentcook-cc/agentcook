package cc.agentcook.application.port.in;

import cc.agentcook.domain.plugin.PluginStatus;

/**
 * Input Port query: list plugins, optionally filtered by status.
 * {@code status} may be {@code null} to mean "any status".
 */
public record ListPluginsQuery(PluginStatus status) {
}
