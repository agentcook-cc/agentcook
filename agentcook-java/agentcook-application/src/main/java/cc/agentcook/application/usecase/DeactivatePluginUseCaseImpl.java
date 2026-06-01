package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PluginNotFoundException;
import cc.agentcook.application.port.in.DeactivatePluginCommand;
import cc.agentcook.application.port.in.DeactivatePluginUseCase;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class DeactivatePluginUseCaseImpl implements DeactivatePluginUseCase {

    private final PluginRepository pluginRepository;

    public DeactivatePluginUseCaseImpl(PluginRepository pluginRepository) {
        this.pluginRepository = pluginRepository;
    }

    @Override
    public Plugin execute(DeactivatePluginCommand command) {
        PluginId pluginId = PluginId.from(command.pluginId());
        Plugin plugin = pluginRepository.findById(pluginId)
                .orElseThrow(() -> new PluginNotFoundException(pluginId));
        plugin.deprecate();
        return pluginRepository.save(plugin);
    }
}
