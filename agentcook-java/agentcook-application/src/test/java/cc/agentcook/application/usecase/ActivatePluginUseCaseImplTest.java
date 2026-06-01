package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.port.in.ActivatePluginCommand;
import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.service.PluginActivationService;
import cc.agentcook.domain.service.PluginActivationService.PluginActivationDeniedException;
import cc.agentcook.domain.user.UserId;
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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ActivatePluginUseCaseImplTest {

    @Mock
    private PluginRepository pluginRepository;

    @Mock
    private PluginActivationService activationService;

    @InjectMocks
    private ActivatePluginUseCaseImpl useCase;

    @Test
    void delegatesToDomainServiceAndReturnsConnectorId() {
        UserId userId = UserId.generate();
        Plugin plugin = Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, "test");
        Connector connector = Connector.establish(plugin.getId(), plugin.getKind(), "{}");

        when(pluginRepository.findById(plugin.getId())).thenReturn(Optional.of(plugin));
        when(activationService.activatePlugin(eq(userId), eq(plugin), any())).thenReturn(connector);

        ConnectorId returned = useCase.execute(new ActivatePluginCommand(
                userId.value().toString(),
                plugin.getId().value().toString(),
                "{}"));

        assertEquals(connector.getId(), returned);
        verify(activationService).activatePlugin(eq(userId), eq(plugin), eq("{}"));
    }

    @Test
    void rejectsMalformedPluginIdString() {
        UserId userId = UserId.generate();

        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new ActivatePluginCommand(
                        userId.value().toString(), "not-a-uuid", "{}")));

        verifyNoInteractions(pluginRepository, activationService);
    }

    @Test
    void rejectsUnknownPluginId() {
        UserId userId = UserId.generate();
        PluginId pluginId = PluginId.from(UUID.randomUUID());
        when(pluginRepository.findById(pluginId)).thenReturn(Optional.empty());

        assertThrows(PluginNotFoundException.class,
                () -> useCase.execute(new ActivatePluginCommand(
                        userId.value().toString(),
                        pluginId.value().toString(),
                        "{}")));

        verifyNoInteractions(activationService);
    }

    @Test
    void propagatesActivationDeniedFromDomainService() {
        UserId userId = UserId.generate();
        Plugin plugin = Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, "test");

        when(pluginRepository.findById(plugin.getId())).thenReturn(Optional.of(plugin));
        when(activationService.activatePlugin(eq(userId), eq(plugin), any()))
                .thenThrow(new PluginActivationDeniedException(userId, plugin.getName()));

        assertThrows(PluginActivationDeniedException.class,
                () -> useCase.execute(new ActivatePluginCommand(
                        userId.value().toString(),
                        plugin.getId().value().toString(),
                        "{}")));
    }
}
