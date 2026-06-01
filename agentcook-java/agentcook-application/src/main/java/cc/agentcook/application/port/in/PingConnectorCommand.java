package cc.agentcook.application.port.in;

import java.util.Objects;

public record PingConnectorCommand(String connectorId) {

    public PingConnectorCommand {
        Objects.requireNonNull(connectorId, "connectorId must not be null");
    }
}
