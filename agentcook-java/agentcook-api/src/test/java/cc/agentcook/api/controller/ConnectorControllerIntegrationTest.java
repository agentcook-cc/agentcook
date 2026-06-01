package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ConnectorControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private PluginRepository pluginRepository;

    @Test
    void createsConnectorForExistingPlugin() throws Exception {
        Plugin plugin = pluginRepository.save(
                Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, "test"));

        mockMvc.perform(post("/api/v1/connectors")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"pluginId":"%s","connectorConfig":"{\\"webhook_url\\":\\"https://example.com\\"}"}
                                """.formatted(plugin.getId().value())))
                .andExpect(status().isCreated())
                .andExpect(header().exists("Location"))
                .andExpect(jsonPath("$.pluginId").value(plugin.getId().value().toString()))
                .andExpect(jsonPath("$.status").value("CONNECTED"));
    }

    @Test
    void returns404WhenCreatingForUnknownPlugin() throws Exception {
        mockMvc.perform(post("/api/v1/connectors")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"pluginId":"00000000-0000-0000-0000-000000000000","connectorConfig":"{}"}
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("PLUGIN_NOT_FOUND"));
    }

    @Test
    void listsConnectorsByPluginId() throws Exception {
        Plugin plugin = pluginRepository.save(
                Plugin.create("feishu-bot", "1.0.0", PluginKind.WEBHOOK, null));

        // Seed one connector via the controller path so the full stack is exercised.
        mockMvc.perform(post("/api/v1/connectors")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"pluginId":"%s","connectorConfig":"cfg"}
                                """.formatted(plugin.getId().value())))
                .andExpect(status().isCreated());

        mockMvc.perform(get("/api/v1/connectors").param("pluginId", plugin.getId().value().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].status").value("CONNECTED"));
    }
}
