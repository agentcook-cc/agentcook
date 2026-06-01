package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListConnectorsQuery;
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
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ListConnectorsUseCaseImplTest {

    @Mock private ConnectorRepository connectorRepository;
    @InjectMocks private ListConnectorsUseCaseImpl useCase;

    @Test
    void listsConnectorsForPlugin() {
        PluginId pluginId = PluginId.generate();
        Connector c = Connector.reconstitute(ConnectorId.generate(), pluginId, PluginKind.WEBHOOK,
                "{}", ConnectorStatus.CONNECTED, Instant.now(), Instant.now(), Instant.now());
        when(connectorRepository.findByPluginId(pluginId)).thenReturn(List.of(c));

        List<Connector> connectors = useCase.execute(new ListConnectorsQuery(pluginId.value().toString()));

        assertEquals(1, connectors.size());
    }

    @Test
    void returnsEmptyListWhenPluginHasNoConnectors() {
        PluginId pluginId = PluginId.from(UUID.randomUUID());
        when(connectorRepository.findByPluginId(pluginId)).thenReturn(List.of());

        List<Connector> connectors = useCase.execute(new ListConnectorsQuery(pluginId.value().toString()));

        assertEquals(0, connectors.size());
    }

    @Test
    void rejectsMalformedPluginIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new ListConnectorsQuery("not-a-uuid")));

        verify(connectorRepository, never()).findByPluginId(org.mockito.ArgumentMatchers.any());
    }
}
