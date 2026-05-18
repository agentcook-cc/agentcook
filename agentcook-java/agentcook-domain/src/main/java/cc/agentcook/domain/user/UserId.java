package cc.agentcook.domain.user;

import java.util.Objects;
import java.util.UUID;

/**
 * Value Object wrapping a UUID identifier for the User aggregate.
 * Immutable, equality based on the underlying UUID value.
 */
public final class UserId {

    private final UUID value;

    private UserId(UUID value) {
        this.value = Objects.requireNonNull(value, "UserId value must not be null");
    }

    public static UserId generate() {
        return new UserId(UUID.randomUUID());
    }

    public static UserId from(UUID value) {
        return new UserId(value);
    }

    public static UserId from(String value) {
        return new UserId(UUID.fromString(value));
    }

    public UUID value() {
        return value;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        UserId userId = (UserId) other;
        return value.equals(userId.value);
    }

    @Override
    public int hashCode() {
        return value.hashCode();
    }

    @Override
    public String toString() {
        return "UserId(" + value + ")";
    }
}
