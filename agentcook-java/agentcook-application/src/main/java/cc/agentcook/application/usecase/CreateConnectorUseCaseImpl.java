package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.port.in.CreateConnectorCommand;
import cc.agentcook.application.port.in.CreateConnectorUseCase;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class CreateConnectorUseCaseImpl implements CreateConnectorUseCase {

    private final PluginRepository pluginRepository;
    private final ConnectorRepository connectorRepository;

    public CreateConnectorUseCaseImpl(PluginRepository pluginRepository,
                                      ConnectorRepository connectorRepository) {
        this.pluginRepository = pluginRepository;
        this.connectorRepository = connectorRepository;
    }

    @Override
    public Connector execute(CreateConnectorCommand command) {
        PluginId pluginId = PluginId.from(command.pluginId());
        Plugin plugin = pluginRepository.findById(pluginId)
                .orElseThrow(() -> new PluginNotFoundException(pluginId));
        Connector connector = Connector.establish(pluginId, plugin.getKind(), command.connectorConfig());
        return connectorRepository.save(connector);
    }
}
