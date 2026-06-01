package cc.agentcook.domain.connector.event;

import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.plugin.PluginId;

import java.time.Instant;

/**
 * Domain Event raised when a Connector is successfully established.
 */
public record ConnectorEstablishedEvent(
        ConnectorId connectorId,
        PluginId pluginId,
        Instant occurredAt
) {
    public ConnectorEstablishedEvent {
        if (connectorId == null) throw new IllegalArgumentException("connectorId must not be null");
        if (pluginId == null) throw new IllegalArgumentException("pluginId must not be null");
        if (occurredAt == null) occurredAt = Instant.now();
    }

    public ConnectorEstablishedEvent(ConnectorId connectorId, PluginId pluginId) {
        this(connectorId, pluginId, Instant.now());
    }
}
