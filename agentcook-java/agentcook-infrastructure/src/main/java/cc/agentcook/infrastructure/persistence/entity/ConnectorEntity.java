package cc.agentcook.infrastructure.persistence.entity;

import cc.agentcook.domain.connector.ConnectorStatus;
import cc.agentcook.domain.plugin.PluginKind;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "connectors", indexes = {
        @Index(name = "idx_connectors_plugin_id", columnList = "plugin_id")
})
public class ConnectorEntity {

    @Id
    @Column(name = "id", columnDefinition = "uuid", nullable = false, updatable = false)
    private UUID id;

    @Column(name = "plugin_id", columnDefinition = "uuid", nullable = false)
    private UUID pluginId;

    @Enumerated(EnumType.STRING)
    @Column(name = "kind", nullable = false, length = 32)
    private PluginKind kind;

    @Column(name = "config", columnDefinition = "text")
    private String config;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private ConnectorStatus status;

    @Column(name = "last_health_check")
    private Instant lastHealthCheck;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected ConnectorEntity() {
    }

    public ConnectorEntity(UUID id, UUID pluginId, PluginKind kind, String config,
                           ConnectorStatus status, Instant lastHealthCheck,
                           Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.pluginId = pluginId;
        this.kind = kind;
        this.config = config;
        this.status = status;
        this.lastHealthCheck = lastHealthCheck;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public UUID getId() { return id; }
    public UUID getPluginId() { return pluginId; }
    public PluginKind getKind() { return kind; }
    public String getConfig() { return config; }
    public ConnectorStatus getStatus() { return status; }
    public Instant getLastHealthCheck() { return lastHealthCheck; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public void setConfig(String config) { this.config = config; }
    public void setStatus(ConnectorStatus status) { this.status = status; }
    public void setLastHealthCheck(Instant lastHealthCheck) { this.lastHealthCheck = lastHealthCheck; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
