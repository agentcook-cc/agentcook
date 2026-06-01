package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.infrastructure.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ConnectorRepositoryAdapterIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ConnectorRepositoryAdapter adapter;

    @Autowired
    private PluginRepositoryAdapter pluginAdapter;

    @Test
    void savesAndReadsBackConnector() {
        Plugin plugin = pluginAdapter.save(Plugin.create("dingtalk", "1.0", PluginKind.WEBHOOK, null));
        Connector connector = Connector.establish(plugin.getId(), plugin.getKind(), "{\"token\":\"x\"}");

        Connector saved = adapter.save(connector);

        assertTrue(adapter.findById(saved.getId()).isPresent());
        assertEquals("{\"token\":\"x\"}", adapter.findById(saved.getId()).get().getConfig());
    }

    @Test
    void findsConnectorsByPluginId() {
        Plugin plugin = pluginAdapter.save(Plugin.create("feishu", "1.0", PluginKind.WEBHOOK, null));
        adapter.save(Connector.establish(plugin.getId(), plugin.getKind(), "cfg1"));
        adapter.save(Connector.establish(plugin.getId(), plugin.getKind(), "cfg2"));

        List<Connector> connectors = adapter.findByPluginId(plugin.getId());

        assertEquals(2, connectors.size());
    }
}
