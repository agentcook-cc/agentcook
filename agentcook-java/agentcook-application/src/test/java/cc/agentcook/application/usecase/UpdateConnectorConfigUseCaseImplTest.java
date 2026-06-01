package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.ConnectorNotFoundException;
import cc.agentcook.application.port.in.UpdateConnectorConfigCommand;
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

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class UpdateConnectorConfigUseCaseImplTest {

    @Mock private ConnectorRepository connectorRepository;
    @InjectMocks private UpdateConnectorConfigUseCaseImpl useCase;

    @Test
    void updatesConfigOfExistingConnector() {
        ConnectorId connectorId = ConnectorId.generate();
        Connector connector = Connector.reconstitute(connectorId, PluginId.generate(), PluginKind.WEBHOOK,
                "old", ConnectorStatus.CONNECTED, Instant.now(), Instant.now(), Instant.now());
        when(connectorRepository.findById(connectorId)).thenReturn(Optional.of(connector));
        when(connectorRepository.save(any(Connector.class))).thenAnswer(inv -> inv.getArgument(0));

        Connector updated = useCase.execute(new UpdateConnectorConfigCommand(
                connectorId.value().toString(), "new"));

        assertEquals("new", updated.getConfig());
        verify(connectorRepository).save(connector);
    }

    @Test
    void rejectsUnknownConnectorId() {
        ConnectorId connectorId = ConnectorId.from(UUID.randomUUID());
        when(connectorRepository.findById(connectorId)).thenReturn(Optional.empty());

        assertThrows(ConnectorNotFoundException.class,
                () -> useCase.execute(new UpdateConnectorConfigCommand(
                        connectorId.value().toString(), "x")));

        verify(connectorRepository, never()).save(any(Connector.class));
    }

    @Test
    void rejectsMalformedConnectorIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new UpdateConnectorConfigCommand("not-a-uuid", "x")));

        verify(connectorRepository, never()).save(any(Connector.class));
    }
}
