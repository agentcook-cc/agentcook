package cc.agentcook.application.port.in;

import java.util.Objects;

public record UpdateConnectorConfigCommand(String connectorId, String config) {

    public UpdateConnectorConfigCommand {
        Objects.requireNonNull(connectorId, "connectorId must not be null");
    }
}
