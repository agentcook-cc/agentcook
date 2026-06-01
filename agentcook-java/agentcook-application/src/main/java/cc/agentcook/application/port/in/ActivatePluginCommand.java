package cc.agentcook.application.port.in;

import java.util.Objects;

public record ActivatePluginCommand(String userId, String pluginId, String connectorConfig) {

    public ActivatePluginCommand {
        Objects.requireNonNull(userId, "userId must not be null");
        Objects.requireNonNull(pluginId, "pluginId must not be null");
    }
}
