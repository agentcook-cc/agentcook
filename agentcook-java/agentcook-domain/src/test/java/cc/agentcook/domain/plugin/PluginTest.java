package cc.agentcook.domain.plugin;

import cc.agentcook.domain.plugin.event.PluginPublishedEvent;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class PluginTest {

    @Test
    void create_shouldSetDraftStatus() {
        Plugin plugin = Plugin.create("weather-plugin", "1.0.0", PluginKind.HTTP, "Weather info");

        assertNotNull(plugin.getId());
        assertEquals("weather-plugin", plugin.getName());
        assertEquals("1.0.0", plugin.getVersion());
        assertEquals(PluginKind.HTTP, plugin.getKind());
        assertEquals(PluginStatus.DRAFT, plugin.getStatus());
        assertTrue(plugin.getDomainEvents().isEmpty());
    }

    @Test
    void create_withBlankName_shouldThrow() {
        assertThrows(IllegalArgumentException.class,
                () -> Plugin.create("", "1.0.0", PluginKind.MCP, "desc"));
    }

    @Test
    void create_withBlankVersion_shouldThrow() {
        assertThrows(IllegalArgumentException.class,
                () -> Plugin.create("name", "", PluginKind.MCP, "desc"));
    }

    @Test
    void publish_draftPlugin_shouldTransitionAndRaiseEvent() {
        Plugin plugin = Plugin.create("mcp-tools", "2.0.0", PluginKind.MCP, "MCP tools");
        plugin.publish();

        assertEquals(PluginStatus.PUBLISHED, plugin.getStatus());
        assertEquals(1, plugin.getDomainEvents().size());
        assertInstanceOf(PluginPublishedEvent.class, plugin.getDomainEvents().get(0));
    }

    @Test
    void publish_deprecatedPlugin_shouldThrow() {
        Plugin plugin = Plugin.create("old", "0.1.0", PluginKind.WEBHOOK, "old");
        plugin.publish();
        plugin.deprecate();
        assertThrows(IllegalStateException.class, plugin::publish);
    }

    @Test
    void deprecate_publishedPlugin_shouldTransition() {
        Plugin plugin = Plugin.create("tool", "1.0.0", PluginKind.OAUTH, "tool");
        plugin.publish();
        plugin.deprecate();
        assertEquals(PluginStatus.DEPRECATED, plugin.getStatus());
    }

    @Test
    void deprecate_draftPlugin_shouldThrow() {
        Plugin plugin = Plugin.create("tool", "1.0.0", PluginKind.HTTP, "tool");
        assertThrows(IllegalStateException.class, plugin::deprecate);
    }

    @Test
    void equals_sameId_shouldBeEqual() {
        PluginId id = PluginId.generate();
        Plugin p1 = Plugin.reconstitute(id, "a", "1.0", PluginKind.MCP, "d", PluginStatus.DRAFT,
                java.time.Instant.now(), java.time.Instant.now());
        Plugin p2 = Plugin.reconstitute(id, "b", "2.0", PluginKind.HTTP, "x", PluginStatus.PUBLISHED,
                java.time.Instant.now(), java.time.Instant.now());
        assertEquals(p1, p2);
    }
}
