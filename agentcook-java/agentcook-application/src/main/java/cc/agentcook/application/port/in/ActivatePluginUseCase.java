package cc.agentcook.application.port.in;

import cc.agentcook.domain.connector.ConnectorId;

/**
 * Input Port: activate a registered plugin for a user
 * (delegates to {@code PluginActivationService} domain service).
 */
public interface ActivatePluginUseCase {

    ConnectorId execute(ActivatePluginCommand command);
}
