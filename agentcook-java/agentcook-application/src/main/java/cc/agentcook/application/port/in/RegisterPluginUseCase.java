package cc.agentcook.application.port.in;

import cc.agentcook.domain.plugin.Plugin;

/**
 * Input Port: register a plugin uploaded as a zip package.
 * Domain validation enforces non-blank name + version.
 */
public interface RegisterPluginUseCase {

    Plugin execute(RegisterPluginCommand command);
}
