package cc.agentcook.domain.connector;

import java.util.Objects;
import java.util.UUID;

/**
 * Value Object wrapping a UUID identifier for the Connector aggregate.
 */
public final class ConnectorId {

    private final UUID value;

    private ConnectorId(UUID value) {
        this.value = Objects.requireNonNull(value, "ConnectorId value must not be null");
    }

    public static ConnectorId generate() {
        return new ConnectorId(UUID.randomUUID());
    }

    public static ConnectorId from(UUID value) {
        return new ConnectorId(value);
    }

    public static ConnectorId from(String value) {
        return new ConnectorId(UUID.fromString(value));
    }

    public UUID value() {
        return value;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        ConnectorId that = (ConnectorId) other;
        return value.equals(that.value);
    }

    @Override
    public int hashCode() {
        return value.hashCode();
    }

    @Override
    public String toString() {
        return "ConnectorId(" + value + ")";
    }
}
