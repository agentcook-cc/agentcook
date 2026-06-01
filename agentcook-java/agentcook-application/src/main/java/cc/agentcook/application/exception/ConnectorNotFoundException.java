package cc.agentcook.application.exception;

import cc.agentcook.domain.connector.ConnectorId;

public class ConnectorNotFoundException extends RuntimeException {

    public ConnectorNotFoundException(ConnectorId connectorId) {
        super("Connector not found: " + connectorId);
    }
}
