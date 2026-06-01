package cc.agentcook.application.port.in;

import cc.agentcook.domain.plugin.Plugin;

/**
 * Input Port: deprecate a published plugin. Only PUBLISHED plugins
 * may be deprecated — the domain layer enforces that invariant.
 */
public interface DeactivatePluginUseCase {

    Plugin execute(DeactivatePluginCommand command);
}
