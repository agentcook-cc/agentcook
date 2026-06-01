package cc.agentcook.application.port.in;

import java.util.Objects;

public record DeleteConnectorCommand(String connectorId) {

    public DeleteConnectorCommand {
        Objects.requireNonNull(connectorId, "connectorId must not be null");
    }
}
