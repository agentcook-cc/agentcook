package cc.agentcook.application.port.in;

import java.util.Objects;

public record DeactivatePluginCommand(String pluginId) {

    public DeactivatePluginCommand {
        Objects.requireNonNull(pluginId, "pluginId must not be null");
    }
}
