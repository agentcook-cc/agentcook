package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.port.in.ActivatePluginCommand;
import cc.agentcook.application.port.in.ActivatePluginUseCase;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.service.PluginActivationService;
import cc.agentcook.domain.user.UserId;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class ActivatePluginUseCaseImpl implements ActivatePluginUseCase {

    private final PluginRepository pluginRepository;
    private final PluginActivationService activationService;

    public ActivatePluginUseCaseImpl(PluginRepository pluginRepository,
                                     PluginActivationService activationService) {
        this.pluginRepository = pluginRepository;
        this.activationService = activationService;
    }

    @Override
    public ConnectorId execute(ActivatePluginCommand command) {
        UserId userId = UserId.from(command.userId());
        PluginId pluginId = PluginId.from(command.pluginId());
        Plugin plugin = pluginRepository.findById(pluginId)
                .orElseThrow(() -> new PluginNotFoundException(pluginId));
        Connector connector = activationService.activatePlugin(userId, plugin, command.connectorConfig());
        return connector.getId();
    }
}
