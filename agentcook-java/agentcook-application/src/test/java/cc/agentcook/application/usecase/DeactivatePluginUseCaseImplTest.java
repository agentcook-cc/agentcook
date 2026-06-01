package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.port.in.DeactivatePluginCommand;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.plugin.PluginStatus;
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
class DeactivatePluginUseCaseImplTest {

    @Mock private PluginRepository pluginRepository;
    @InjectMocks private DeactivatePluginUseCaseImpl useCase;

    @Test
    void deprecatesPublishedPlugin() {
        Plugin plugin = Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, "x");
        plugin.publish();
        when(pluginRepository.findById(plugin.getId())).thenReturn(Optional.of(plugin));
        when(pluginRepository.save(any(Plugin.class))).thenAnswer(inv -> inv.getArgument(0));

        Plugin deprecated = useCase.execute(new DeactivatePluginCommand(plugin.getId().value().toString()));

        assertEquals(PluginStatus.DEPRECATED, deprecated.getStatus());
        verify(pluginRepository).save(plugin);
    }

    @Test
    void rejectsUnknownPluginId() {
        PluginId pluginId = PluginId.from(UUID.randomUUID());
        when(pluginRepository.findById(pluginId)).thenReturn(Optional.empty());

        assertThrows(PluginNotFoundException.class,
                () -> useCase.execute(new DeactivatePluginCommand(pluginId.value().toString())));

        verify(pluginRepository, never()).save(any(Plugin.class));
    }

    @Test
    void rejectsDeprecatingDraftPluginPerDomainInvariant() {
        Plugin draft = Plugin.create("draft-bot", "0.1.0", PluginKind.HTTP, "draft");
        when(pluginRepository.findById(draft.getId())).thenReturn(Optional.of(draft));

        assertThrows(IllegalStateException.class,
                () -> useCase.execute(new DeactivatePluginCommand(draft.getId().value().toString())));

        verify(pluginRepository, never()).save(any(Plugin.class));
    }
}
