package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.ConnectorNotFoundException;
import cc.agentcook.application.port.in.DeleteConnectorCommand;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.connector.ConnectorStatus;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginKind;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeleteConnectorUseCaseImplTest {

    @Mock private ConnectorRepository connectorRepository;
    @InjectMocks private DeleteConnectorUseCaseImpl useCase;

    @Test
    void deletesExistingConnector() {
        ConnectorId connectorId = ConnectorId.generate();
        Connector existing = Connector.reconstitute(connectorId, PluginId.generate(), PluginKind.WEBHOOK,
                "{}", ConnectorStatus.CONNECTED, Instant.now(), Instant.now(), Instant.now());
        when(connectorRepository.findById(connectorId)).thenReturn(Optional.of(existing));

        useCase.execute(new DeleteConnectorCommand(connectorId.value().toString()));

        verify(connectorRepository).delete(connectorId);
    }

    @Test
    void rejectsUnknownConnectorId() {
        ConnectorId connectorId = ConnectorId.from(UUID.randomUUID());
        when(connectorRepository.findById(connectorId)).thenReturn(Optional.empty());

        assertThrows(ConnectorNotFoundException.class,
                () -> useCase.execute(new DeleteConnectorCommand(connectorId.value().toString())));

        verify(connectorRepository, never()).delete(connectorId);
    }

    @Test
    void rejectsMalformedConnectorIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new DeleteConnectorCommand("not-a-uuid")));

        verify(connectorRepository, never()).delete(org.mockito.ArgumentMatchers.any());
    }
}
