package cc.agentcook.application.exception;

import cc.agentcook.domain.plugin.PluginId;

public class PluginNotFoundException extends RuntimeException {

    public PluginNotFoundException(PluginId pluginId) {
        super("Plugin not found: " + pluginId);
    }
}
