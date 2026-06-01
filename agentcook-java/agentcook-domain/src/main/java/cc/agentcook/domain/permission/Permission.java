package cc.agentcook.domain.permission;

import cc.agentcook.domain.user.UserId;

import java.time.Instant;
import java.util.Objects;

/**
 * Permission Aggregate Root.
 * Represents an RBAC rule granting or denying access to a resource action.
 */
public class Permission {

    private final PermissionId id;
    private final UserId userId;
    private final String resource;
    private final String action;
    private final PermissionEffect effect;
    private final Instant createdAt;

    private Permission(PermissionId id, UserId userId, String resource, String action, PermissionEffect effect, Instant createdAt) {
        this.id = Objects.requireNonNull(id);
        this.userId = Objects.requireNonNull(userId);
        this.resource = Objects.requireNonNull(resource);
        this.action = Objects.requireNonNull(action);
        this.effect = Objects.requireNonNull(effect);
        this.createdAt = Objects.requireNonNull(createdAt);
    }

    /**
     * Factory: grant a permission.
     */
    public static Permission grant(UserId userId, String resource, String action) {
        if (resource == null || resource.isBlank()) throw new IllegalArgumentException("resource must not be blank");
        if (action == null || action.isBlank()) throw new IllegalArgumentException("action must not be blank");
        return new Permission(PermissionId.generate(), userId, resource, action, PermissionEffect.ALLOW, Instant.now());
    }

    /**
     * Factory: deny a permission.
     */
    public static Permission deny(UserId userId, String resource, String action) {
        if (resource == null || resource.isBlank()) throw new IllegalArgumentException("resource must not be blank");
        if (action == null || action.isBlank()) throw new IllegalArgumentException("action must not be blank");
        return new Permission(PermissionId.generate(), userId, resource, action, PermissionEffect.DENY, Instant.now());
    }

    public static Permission reconstitute(PermissionId id, UserId userId, String resource, String action, PermissionEffect effect, Instant createdAt) {
        return new Permission(id, userId, resource, action, effect, createdAt);
    }

    public boolean isAllowed() {
        return effect == PermissionEffect.ALLOW;
    }

    public boolean matches(String resource, String action) {
        return this.resource.equals(resource) && this.action.equals(action);
    }

    // --- Getters ---

    public PermissionId getId() { return id; }
    public UserId getUserId() { return userId; }
    public String getResource() { return resource; }
    public String getAction() { return action; }
    public PermissionEffect getEffect() { return effect; }
    public Instant getCreatedAt() { return createdAt; }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        Permission that = (Permission) other;
        return id.equals(that.id);
    }

    @Override
    public int hashCode() {
        return id.hashCode();
    }

    @Override
    public String toString() {
        return "Permission{id=" + id + ", userId=" + userId + ", resource='" + resource + "', action='" + action + "', effect=" + effect + "}";
    }
}
