package cc.agentcook.domain.connector;

import cc.agentcook.domain.connector.event.ConnectorEstablishedEvent;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginKind;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Connector Aggregate Root.
 * Represents an IM channel integration (DingTalk/Feishu/Telegram/Discord).
 */
public class Connector {

    private final ConnectorId id;
    private final PluginId pluginId;
    private final PluginKind kind;
    private String config;
    private ConnectorStatus status;
    private Instant lastHealthCheck;
    private final Instant createdAt;
    private Instant updatedAt;

    private final List<Object> domainEvents = new ArrayList<>();

    private Connector(ConnectorId id, PluginId pluginId, PluginKind kind, String config,
                      ConnectorStatus status, Instant lastHealthCheck, Instant createdAt, Instant updatedAt) {
        this.id = Objects.requireNonNull(id);
        this.pluginId = Objects.requireNonNull(pluginId);
        this.kind = Objects.requireNonNull(kind);
        this.config = config;
        this.status = Objects.requireNonNull(status);
        this.lastHealthCheck = lastHealthCheck;
        this.createdAt = Objects.requireNonNull(createdAt);
        this.updatedAt = Objects.requireNonNull(updatedAt);
    }

    /**
     * Factory: establish a new Connector (raises ConnectorEstablishedEvent).
     */
    public static Connector establish(PluginId pluginId, PluginKind kind, String config) {
        if (pluginId == null) throw new IllegalArgumentException("pluginId must not be null");
        ConnectorId id = ConnectorId.generate();
        Instant now = Instant.now();
        Connector connector = new Connector(id, pluginId, kind, config, ConnectorStatus.CONNECTED, now, now, now);
        connector.domainEvents.add(new ConnectorEstablishedEvent(id, pluginId, now));
        return connector;
    }

    public static Connector reconstitute(ConnectorId id, PluginId pluginId, PluginKind kind, String config,
                                         ConnectorStatus status, Instant lastHealthCheck, Instant createdAt, Instant updatedAt) {
        return new Connector(id, pluginId, kind, config, status, lastHealthCheck, createdAt, updatedAt);
    }

    public void disconnect() {
        this.status = ConnectorStatus.DISCONNECTED;
        this.updatedAt = Instant.now();
    }

    public void markError() {
        this.status = ConnectorStatus.ERROR;
        this.updatedAt = Instant.now();
    }

    public void reconnect() {
        this.status = ConnectorStatus.CONNECTED;
        this.lastHealthCheck = Instant.now();
        this.updatedAt = Instant.now();
    }

    public void recordHealthCheck() {
        this.lastHealthCheck = Instant.now();
        this.updatedAt = Instant.now();
    }

    public void updateConfig(String config) {
        this.config = config;
        this.updatedAt = Instant.now();
    }

    // --- Getters ---

    public ConnectorId getId() { return id; }
    public PluginId getPluginId() { return pluginId; }
    public PluginKind getKind() { return kind; }
    public String getConfig() { return config; }
    public ConnectorStatus getStatus() { return status; }
    public Instant getLastHealthCheck() { return lastHealthCheck; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public List<Object> getDomainEvents() {
        return Collections.unmodifiableList(domainEvents);
    }

    public void clearDomainEvents() {
        domainEvents.clear();
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        Connector that = (Connector) other;
        return id.equals(that.id);
    }

    @Override
    public int hashCode() {
        return id.hashCode();
    }

    @Override
    public String toString() {
        return "Connector{id=" + id + ", pluginId=" + pluginId + ", kind=" + kind + ", status=" + status + "}";
    }
}
