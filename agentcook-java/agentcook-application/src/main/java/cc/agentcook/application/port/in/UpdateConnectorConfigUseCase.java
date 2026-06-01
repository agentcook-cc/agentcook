package cc.agentcook.application.port.in;

import cc.agentcook.domain.connector.Connector;

public interface UpdateConnectorConfigUseCase {

    Connector execute(UpdateConnectorConfigCommand command);
}
