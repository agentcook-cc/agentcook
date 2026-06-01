package cc.agentcook.domain.connector;

import cc.agentcook.domain.connector.event.ConnectorEstablishedEvent;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginKind;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ConnectorTest {

    @Test
    void establish_shouldSetConnectedAndRaiseEvent() {
        PluginId pluginId = PluginId.generate();
        Connector connector = Connector.establish(pluginId, PluginKind.MCP, "{\"url\":\"http://localhost\"}");

        assertNotNull(connector.getId());
        assertEquals(pluginId, connector.getPluginId());
        assertEquals(PluginKind.MCP, connector.getKind());
        assertEquals(ConnectorStatus.CONNECTED, connector.getStatus());
        assertEquals(1, connector.getDomainEvents().size());
        assertInstanceOf(ConnectorEstablishedEvent.class, connector.getDomainEvents().get(0));
    }

    @Test
    void establish_withNullPluginId_shouldThrow() {
        assertThrows(IllegalArgumentException.class,
                () -> Connector.establish(null, PluginKind.HTTP, "{}"));
    }

    @Test
    void disconnect_shouldTransition() {
        Connector connector = Connector.establish(PluginId.generate(), PluginKind.OAUTH, "{}");
        connector.disconnect();
        assertEquals(ConnectorStatus.DISCONNECTED, connector.getStatus());
    }

    @Test
    void markError_shouldTransition() {
        Connector connector = Connector.establish(PluginId.generate(), PluginKind.WEBHOOK, "{}");
        connector.markError();
        assertEquals(ConnectorStatus.ERROR, connector.getStatus());
    }

    @Test
    void reconnect_shouldTransitionBackToConnected() {
        Connector connector = Connector.establish(PluginId.generate(), PluginKind.HTTP, "{}");
        connector.disconnect();
        connector.reconnect();
        assertEquals(ConnectorStatus.CONNECTED, connector.getStatus());
        assertNotNull(connector.getLastHealthCheck());
    }

    @Test
    void equals_sameId_shouldBeEqual() {
        ConnectorId id = ConnectorId.generate();
        Connector c1 = Connector.reconstitute(id, PluginId.generate(), PluginKind.MCP, "{}", ConnectorStatus.CONNECTED, null, java.time.Instant.now(), java.time.Instant.now());
        Connector c2 = Connector.reconstitute(id, PluginId.generate(), PluginKind.HTTP, "{}", ConnectorStatus.ERROR, null, java.time.Instant.now(), java.time.Instant.now());
        assertEquals(c1, c2);
    }
}
