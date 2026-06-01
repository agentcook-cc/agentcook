package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.ConnectorNotFoundException;
import cc.agentcook.application.port.in.UpdateConnectorConfigCommand;
import cc.agentcook.application.port.in.UpdateConnectorConfigUseCase;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.connector.ConnectorRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class UpdateConnectorConfigUseCaseImpl implements UpdateConnectorConfigUseCase {

    private final ConnectorRepository connectorRepository;

    public UpdateConnectorConfigUseCaseImpl(ConnectorRepository connectorRepository) {
        this.connectorRepository = connectorRepository;
    }

    @Override
    public Connector execute(UpdateConnectorConfigCommand command) {
        ConnectorId connectorId = ConnectorId.from(command.connectorId());
        Connector connector = connectorRepository.findById(connectorId)
                .orElseThrow(() -> new ConnectorNotFoundException(connectorId));
        connector.updateConfig(command.config());
        return connectorRepository.save(connector);
    }
}
