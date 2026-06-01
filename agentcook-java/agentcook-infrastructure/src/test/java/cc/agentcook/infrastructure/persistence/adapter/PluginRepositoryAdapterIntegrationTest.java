package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginStatus;
import cc.agentcook.infrastructure.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PluginRepositoryAdapterIntegrationTest extends IntegrationTestBase {

    @Autowired
    private PluginRepositoryAdapter adapter;

    @Test
    void savesAndReconstitutesPluginPreservingStatus() {
        Plugin plugin = Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, "test");
        plugin.publish();
        Plugin saved = adapter.save(plugin);

        Optional<Plugin> loaded = adapter.findById(saved.getId());

        assertTrue(loaded.isPresent());
        assertEquals(PluginStatus.PUBLISHED, loaded.get().getStatus());
    }

    @Test
    void findsByNameAndVersion() {
        adapter.save(Plugin.create("feishu-bot", "2.0.0", PluginKind.WEBHOOK, null));

        Optional<Plugin> hit = adapter.findByNameAndVersion("feishu-bot", "2.0.0");
        Optional<Plugin> miss = adapter.findByNameAndVersion("feishu-bot", "9.9.9");

        assertTrue(hit.isPresent());
        assertTrue(miss.isEmpty());
    }

    @Test
    void filtersByStatus() {
        Plugin published = Plugin.create("p1", "1.0", PluginKind.HTTP, null);
        published.publish();
        adapter.save(published);
        adapter.save(Plugin.create("p2", "1.0", PluginKind.HTTP, null));

        List<Plugin> publishedList = adapter.findByStatus(PluginStatus.PUBLISHED);

        assertEquals(1, publishedList.size());
    }
}
