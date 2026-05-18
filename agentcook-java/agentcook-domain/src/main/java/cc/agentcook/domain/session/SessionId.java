package cc.agentcook.domain.session;

import java.util.Objects;
import java.util.UUID;

/**
 * Value Object wrapping a UUID identifier for the Session aggregate.
 */
public final class SessionId {

    private final UUID value;

    private SessionId(UUID value) {
        this.value = Objects.requireNonNull(value, "SessionId value must not be null");
    }

    public static SessionId generate() {
        return new SessionId(UUID.randomUUID());
    }

    public static SessionId from(UUID value) {
        return new SessionId(value);
    }

    public static SessionId from(String value) {
        return new SessionId(UUID.fromString(value));
    }

    public UUID value() {
        return value;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        SessionId that = (SessionId) other;
        return value.equals(that.value);
    }

    @Override
    public int hashCode() {
        return value.hashCode();
    }

    @Override
    public String toString() {
        return "SessionId(" + value + ")";
    }
}
