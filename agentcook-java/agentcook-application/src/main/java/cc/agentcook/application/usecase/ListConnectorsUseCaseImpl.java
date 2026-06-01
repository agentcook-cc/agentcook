package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListConnectorsQuery;
import cc.agentcook.application.port.in.ListConnectorsUseCase;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.plugin.PluginId;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ListConnectorsUseCaseImpl implements ListConnectorsUseCase {

    private final ConnectorRepository connectorRepository;

    public ListConnectorsUseCaseImpl(ConnectorRepository connectorRepository) {
        this.connectorRepository = connectorRepository;
    }

    @Override
    public List<Connector> execute(ListConnectorsQuery query) {
        PluginId pluginId = PluginId.from(query.pluginId());
        return connectorRepository.findByPluginId(pluginId);
    }
}
