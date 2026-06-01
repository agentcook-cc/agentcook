package cc.agentcook.application.port.in;

import java.util.Objects;

public record CreateConnectorCommand(String pluginId, String connectorConfig) {

    public CreateConnectorCommand {
        Objects.requireNonNull(pluginId, "pluginId must not be null");
    }
}
