package cc.agentcook.domain.service;

import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.connector.ConnectorStatus;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.plugin.PluginStatus;
import cc.agentcook.domain.user.UserId;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class PluginActivationServiceTest {

    private PluginActivationService service;
    private InMemoryPermissionRepo permissionRepo;
    private InMemoryConnectorRepo connectorRepo;
    private InMemoryPluginRepo pluginRepo;

    @BeforeEach
    void setUp() {
        permissionRepo = new InMemoryPermissionRepo();
        connectorRepo = new InMemoryConnectorRepo();
        pluginRepo = new InMemoryPluginRepo();
        service = new PluginActivationService(permissionRepo, connectorRepo, pluginRepo);
    }

    @Test
    void activatePlugin_withPermission_shouldPublishAndConnect() {
        UserId userId = UserId.generate();
        Plugin plugin = Plugin.create("weather", "1.0.0", PluginKind.HTTP, "Weather plugin");
        permissionRepo.grantPermission(Permission.grant(userId, "plugin:weather", "activate"));

        Connector connector = service.activatePlugin(userId, plugin, "{\"url\":\"http://api.weather.com\"}");

        assertEquals(PluginStatus.PUBLISHED, plugin.getStatus());
        assertEquals(ConnectorStatus.CONNECTED, connector.getStatus());
        assertEquals(plugin.getId(), connector.getPluginId());
    }

    @Test
    void activatePlugin_withoutPermission_shouldThrow() {
        UserId userId = UserId.generate();
        Plugin plugin = Plugin.create("secret", "1.0.0", PluginKind.MCP, "Secret plugin");

        assertThrows(PluginActivationService.PluginActivationDeniedException.class,
                () -> service.activatePlugin(userId, plugin, "{}"));
    }

    @Test
    void activatePlugin_alreadyDeprecated_shouldThrow() {
        UserId userId = UserId.generate();
        Plugin plugin = Plugin.create("old", "0.1.0", PluginKind.WEBHOOK, "Old");
        plugin.publish();
        plugin.deprecate();
        permissionRepo.grantPermission(Permission.grant(userId, "plugin:old", "activate"));

        assertThrows(IllegalStateException.class,
                () -> service.activatePlugin(userId, plugin, "{}"));
    }

    @Test
    void activatePlugin_denyPermission_shouldThrow() {
        UserId userId = UserId.generate();
        Plugin plugin = Plugin.create("blocked", "1.0.0", PluginKind.OAUTH, "Blocked");
        permissionRepo.grantPermission(Permission.deny(userId, "plugin:blocked", "activate"));

        assertThrows(PluginActivationService.PluginActivationDeniedException.class,
                () -> service.activatePlugin(userId, plugin, "{}"));
    }

    // --- In-memory test doubles ---

    private static class InMemoryPermissionRepo implements PermissionRepository {
        private final java.util.List<Permission> store = new java.util.ArrayList<>();

        void grantPermission(Permission p) { store.add(p); }

        @Override public java.util.Optional<Permission> findById(cc.agentcook.domain.permission.PermissionId id) { return store.stream().filter(p -> p.getId().equals(id)).findFirst(); }
        @Override public List<Permission> findByUserId(UserId userId) { return store.stream().filter(p -> p.getUserId().equals(userId)).toList(); }
        @Override public List<Permission> findByUserIdAndResource(UserId userId, String resource) { return store.stream().filter(p -> p.getUserId().equals(userId) && p.getResource().equals(resource)).toList(); }
        @Override public Permission save(Permission permission) { store.add(permission); return permission; }
        @Override public void delete(cc.agentcook.domain.permission.PermissionId id) { store.removeIf(p -> p.getId().equals(id)); }
    }

    private static class InMemoryConnectorRepo implements ConnectorRepository {
        private final java.util.List<Connector> store = new java.util.ArrayList<>();

        @Override public java.util.Optional<Connector> findById(cc.agentcook.domain.connector.ConnectorId id) { return store.stream().filter(c -> c.getId().equals(id)).findFirst(); }
        @Override public List<Connector> findByPluginId(cc.agentcook.domain.plugin.PluginId pluginId) { return store.stream().filter(c -> c.getPluginId().equals(pluginId)).toList(); }
        @Override public Connector save(Connector connector) { store.add(connector); return connector; }
        @Override public void delete(cc.agentcook.domain.connector.ConnectorId id) { store.removeIf(c -> c.getId().equals(id)); }
    }

    private static class InMemoryPluginRepo implements PluginRepository {
        private final java.util.List<Plugin> store = new java.util.ArrayList<>();

        @Override public java.util.Optional<Plugin> findById(cc.agentcook.domain.plugin.PluginId id) { return store.stream().filter(p -> p.getId().equals(id)).findFirst(); }
        @Override public List<Plugin> findByStatus(PluginStatus status) { return store.stream().filter(p -> p.getStatus().equals(status)).toList(); }
        @Override public java.util.Optional<Plugin> findByNameAndVersion(String name, String version) { return store.stream().filter(p -> p.getName().equals(name) && p.getVersion().equals(version)).findFirst(); }
        @Override public Plugin save(Plugin plugin) { store.add(plugin); return plugin; }
        @Override public void delete(cc.agentcook.domain.plugin.PluginId id) { store.removeIf(p -> p.getId().equals(id)); }
    }
}
