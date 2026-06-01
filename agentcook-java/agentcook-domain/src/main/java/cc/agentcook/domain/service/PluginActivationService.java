package cc.agentcook.domain.service;

import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.user.UserId;

import java.util.List;

/**
 * Domain Service: cross-aggregate orchestration for plugin activation.
 * Checks Permission → Creates Connector → Publishes Plugin.
 */
public class PluginActivationService {

    private final PermissionRepository permissionRepository;
    private final ConnectorRepository connectorRepository;
    private final PluginRepository pluginRepository;

    public PluginActivationService(PermissionRepository permissionRepository,
                                   ConnectorRepository connectorRepository,
                                   PluginRepository pluginRepository) {
        this.permissionRepository = permissionRepository;
        this.connectorRepository = connectorRepository;
        this.pluginRepository = pluginRepository;
    }

    /**
     * Activate a plugin for a user: check permission, establish connector, publish plugin.
     *
     * @throws PluginActivationDeniedException if user lacks permission
     * @throws IllegalStateException if plugin cannot be published
     */
    public Connector activatePlugin(UserId userId, Plugin plugin, String connectorConfig) {
        if (!hasActivatePermission(userId, plugin.getName())) {
            throw new PluginActivationDeniedException(userId, plugin.getName());
        }

        plugin.publish();
        pluginRepository.save(plugin);

        Connector connector = Connector.establish(plugin.getId(), plugin.getKind(), connectorConfig);
        connectorRepository.save(connector);

        return connector;
    }

    private boolean hasActivatePermission(UserId userId, String pluginName) {
        List<Permission> permissions = permissionRepository.findByUserIdAndResource(userId, "plugin:" + pluginName);
        return permissions.stream()
                .anyMatch(p -> p.matches("plugin:" + pluginName, "activate") && p.isAllowed());
    }

    /**
     * Exception for denied plugin activation.
     */
    public static class PluginActivationDeniedException extends RuntimeException {
        public PluginActivationDeniedException(UserId userId, String pluginName) {
            super("User " + userId + " is not allowed to activate plugin: " + pluginName);
        }
    }
}
