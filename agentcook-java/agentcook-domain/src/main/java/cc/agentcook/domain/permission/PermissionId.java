package cc.agentcook.domain.permission;

import java.util.Objects;
import java.util.UUID;

/**
 * Value Object wrapping a UUID identifier for the Permission aggregate.
 */
public final class PermissionId {

    private final UUID value;

    private PermissionId(UUID value) {
        this.value = Objects.requireNonNull(value, "PermissionId value must not be null");
    }

    public static PermissionId generate() {
        return new PermissionId(UUID.randomUUID());
    }

    public static PermissionId from(UUID value) {
        return new PermissionId(value);
    }

    public static PermissionId from(String value) {
        return new PermissionId(UUID.fromString(value));
    }

    public UUID value() {
        return value;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        PermissionId that = (PermissionId) other;
        return value.equals(that.value);
    }

    @Override
    public int hashCode() {
        return value.hashCode();
    }

    @Override
    public String toString() {
        return "PermissionId(" + value + ")";
    }
}
