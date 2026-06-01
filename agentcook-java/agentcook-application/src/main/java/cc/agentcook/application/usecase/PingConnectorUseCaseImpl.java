package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.ConnectorNotFoundException;
import cc.agentcook.application.port.in.PingConnectorCommand;
import cc.agentcook.application.port.in.PingConnectorResult;
import cc.agentcook.application.port.in.PingConnectorUseCase;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.connector.ConnectorRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Phase 3 ping: records a health-check timestamp and returns a mock
 * latency. Phase 4 replaces the latency probe with a real upstream IM
 * call (DingTalk / Feishu / Telegram / Discord SDK).
 */
@Service
@Transactional
public class PingConnectorUseCaseImpl implements PingConnectorUseCase {

    private static final long DEV_PING_LATENCY_MS = 42L;

    private final ConnectorRepository connectorRepository;

    public PingConnectorUseCaseImpl(ConnectorRepository connectorRepository) {
        this.connectorRepository = connectorRepository;
    }

    @Override
    public PingConnectorResult execute(PingConnectorCommand command) {
        ConnectorId connectorId = ConnectorId.from(command.connectorId());
        Connector connector = connectorRepository.findById(connectorId)
                .orElseThrow(() -> new ConnectorNotFoundException(connectorId));
        connector.recordHealthCheck();
        Connector saved = connectorRepository.save(connector);
        return new PingConnectorResult(saved.getStatus(), DEV_PING_LATENCY_MS);
    }
}
