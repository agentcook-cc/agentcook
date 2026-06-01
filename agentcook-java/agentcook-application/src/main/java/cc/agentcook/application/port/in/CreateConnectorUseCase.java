package cc.agentcook.application.port.in;

import cc.agentcook.domain.connector.Connector;

/**
 * Input Port: directly establish a Connector for an existing Plugin
 * (admin path — bypasses {@code PluginActivationService} permission
 * check, which is for end-user activation).
 */
public interface CreateConnectorUseCase {

    Connector execute(CreateConnectorCommand command);
}
