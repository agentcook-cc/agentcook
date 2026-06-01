package cc.agentcook.infrastructure.persistence.entity;

import cc.agentcook.domain.permission.PermissionEffect;
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
@Table(name = "permissions", indexes = {
        @Index(name = "idx_permissions_user_resource", columnList = "user_id, resource")
})
public class PermissionEntity {

    @Id
    @Column(name = "id", columnDefinition = "uuid", nullable = false, updatable = false)
    private UUID id;

    @Column(name = "user_id", columnDefinition = "uuid", nullable = false)
    private UUID userId;

    @Column(name = "resource", nullable = false, length = 255)
    private String resource;

    @Column(name = "action", nullable = false, length = 64)
    private String action;

    @Enumerated(EnumType.STRING)
    @Column(name = "effect", nullable = false, length = 16)
    private PermissionEffect effect;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected PermissionEntity() {
    }

    public PermissionEntity(UUID id, UUID userId, String resource, String action,
                            PermissionEffect effect, Instant createdAt) {
        this.id = id;
        this.userId = userId;
        this.resource = resource;
        this.action = action;
        this.effect = effect;
        this.createdAt = createdAt;
    }

    public UUID getId() { return id; }
    public UUID getUserId() { return userId; }
    public String getResource() { return resource; }
    public String getAction() { return action; }
    public PermissionEffect getEffect() { return effect; }
    public Instant getCreatedAt() { return createdAt; }
}
