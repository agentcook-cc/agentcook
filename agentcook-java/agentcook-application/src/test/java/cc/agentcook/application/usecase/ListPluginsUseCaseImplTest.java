package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListPluginsQuery;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.plugin.PluginStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ListPluginsUseCaseImplTest {

    @Mock private PluginRepository pluginRepository;
    @InjectMocks private ListPluginsUseCaseImpl useCase;

    @Test
    void defaultsToPublishedWhenStatusFilterIsNull() {
        Plugin published = Plugin.create("p", "1.0", PluginKind.WEBHOOK, null);
        published.publish();
        when(pluginRepository.findByStatus(PluginStatus.PUBLISHED)).thenReturn(List.of(published));

        List<Plugin> plugins = useCase.execute(new ListPluginsQuery(null));

        assertEquals(1, plugins.size());
        assertEquals(PluginStatus.PUBLISHED, plugins.get(0).getStatus());
        verify(pluginRepository).findByStatus(PluginStatus.PUBLISHED);
    }

    @Test
    void honorsExplicitStatusFilter() {
        Plugin draft = Plugin.create("draft", "0.1", PluginKind.HTTP, null);
        when(pluginRepository.findByStatus(PluginStatus.DRAFT)).thenReturn(List.of(draft));

        List<Plugin> plugins = useCase.execute(new ListPluginsQuery(PluginStatus.DRAFT));

        assertEquals(1, plugins.size());
        verify(pluginRepository).findByStatus(PluginStatus.DRAFT);
    }

    @Test
    void returnsEmptyListWhenNoPluginsMatch() {
        when(pluginRepository.findByStatus(PluginStatus.DEPRECATED)).thenReturn(List.of());

        List<Plugin> plugins = useCase.execute(new ListPluginsQuery(PluginStatus.DEPRECATED));

        assertEquals(0, plugins.size());
    }
}
