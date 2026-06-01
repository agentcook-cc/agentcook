package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.ConnectorNotFoundException;
import cc.agentcook.application.port.in.DeleteConnectorCommand;
import cc.agentcook.application.port.in.DeleteConnectorUseCase;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.connector.ConnectorRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class DeleteConnectorUseCaseImpl implements DeleteConnectorUseCase {

    private final ConnectorRepository connectorRepository;

    public DeleteConnectorUseCaseImpl(ConnectorRepository connectorRepository) {
        this.connectorRepository = connectorRepository;
    }

    @Override
    public void execute(DeleteConnectorCommand command) {
        ConnectorId connectorId = ConnectorId.from(command.connectorId());
        if (connectorRepository.findById(connectorId).isEmpty()) {
            throw new ConnectorNotFoundException(connectorId);
        }
        connectorRepository.delete(connectorId);
    }
}
