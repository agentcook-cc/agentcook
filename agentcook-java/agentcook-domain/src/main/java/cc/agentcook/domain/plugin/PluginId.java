package cc.agentcook.domain.plugin;

import java.util.Objects;
import java.util.UUID;

/**
 * Value Object wrapping a UUID identifier for the Plugin aggregate.
 */
public final class PluginId {

    private final UUID value;

    private PluginId(UUID value) {
        this.value = Objects.requireNonNull(value, "PluginId value must not be null");
    }

    public static PluginId generate() {
        return new PluginId(UUID.randomUUID());
    }

    public static PluginId from(UUID value) {
        return new PluginId(value);
    }

    public static PluginId from(String value) {
        return new PluginId(UUID.fromString(value));
    }

    public UUID value() {
        return value;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        PluginId that = (PluginId) other;
        return value.equals(that.value);
    }

    @Override
    public int hashCode() {
        return value.hashCode();
    }

    @Override
    public String toString() {
        return "PluginId(" + value + ")";
    }
}
