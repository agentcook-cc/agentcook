package cc.agentcook.domain.plugin.event;

import cc.agentcook.domain.plugin.PluginId;

import java.time.Instant;

/**
 * Domain Event raised when a Plugin transitions to PUBLISHED status.
 */
public record PluginPublishedEvent(
        PluginId pluginId,
        String name,
        String version,
        Instant occurredAt
) {
    public PluginPublishedEvent {
        if (pluginId == null) throw new IllegalArgumentException("pluginId must not be null");
        if (name == null || name.isBlank()) throw new IllegalArgumentException("name must not be blank");
        if (occurredAt == null) occurredAt = Instant.now();
    }

    public PluginPublishedEvent(PluginId pluginId, String name, String version) {
        this(pluginId, name, version, Instant.now());
    }
}
