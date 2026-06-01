package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.port.in.CreateConnectorCommand;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.connector.ConnectorStatus;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CreateConnectorUseCaseImplTest {

    @Mock private PluginRepository pluginRepository;
    @Mock private ConnectorRepository connectorRepository;
    @InjectMocks private CreateConnectorUseCaseImpl useCase;

    @Test
    void establishesConnectorForExistingPlugin() {
        Plugin plugin = Plugin.create("dingtalk", "1.0", PluginKind.WEBHOOK, "x");
        when(pluginRepository.findById(plugin.getId())).thenReturn(Optional.of(plugin));
        when(connectorRepository.save(any(Connector.class))).thenAnswer(inv -> inv.getArgument(0));

        Connector connector = useCase.execute(
                new CreateConnectorCommand(plugin.getId().value().toString(), "{}"));

        assertEquals(ConnectorStatus.CONNECTED, connector.getStatus());
        assertEquals(plugin.getId(), connector.getPluginId());
        verify(connectorRepository).save(any(Connector.class));
    }

    @Test
    void rejectsUnknownPluginId() {
        PluginId pluginId = PluginId.from(UUID.randomUUID());
        when(pluginRepository.findById(pluginId)).thenReturn(Optional.empty());

        assertThrows(PluginNotFoundException.class,
                () -> useCase.execute(new CreateConnectorCommand(pluginId.value().toString(), "{}")));

        verify(connectorRepository, never()).save(any(Connector.class));
    }

    @Test
    void rejectsMalformedPluginIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new CreateConnectorCommand("not-a-uuid", "{}")));

        verify(connectorRepository, never()).save(any(Connector.class));
    }
}
