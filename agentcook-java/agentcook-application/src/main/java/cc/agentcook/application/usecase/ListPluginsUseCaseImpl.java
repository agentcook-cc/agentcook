package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListPluginsQuery;
import cc.agentcook.application.port.in.ListPluginsUseCase;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.plugin.PluginStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ListPluginsUseCaseImpl implements ListPluginsUseCase {

    private final PluginRepository pluginRepository;

    public ListPluginsUseCaseImpl(PluginRepository pluginRepository) {
        this.pluginRepository = pluginRepository;
    }

    @Override
    public List<Plugin> execute(ListPluginsQuery query) {
        PluginStatus statusFilter = query.status() == null ? PluginStatus.PUBLISHED : query.status();
        return pluginRepository.findByStatus(statusFilter);
    }
}
