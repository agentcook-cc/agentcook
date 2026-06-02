package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.UUID;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ConnectorControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private PluginRepository pluginRepository;
    @Autowired private ObjectMapper objectMapper;

    private UUID seedConnector(String pluginName) throws Exception {
        Plugin plugin = pluginRepository.save(
                Plugin.create(pluginName, "1.0.0", PluginKind.WEBHOOK, null));
        MvcResult created = mockMvc.perform(post("/api/v1/connectors")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"pluginId":"%s","connectorConfig":"{\\"k\\":\\"v\\"}"}
                                """.formatted(plugin.getId().value())))
                .andExpect(status().isCreated())
                .andReturn();
        JsonNode body = objectMapper.readTree(created.getResponse().getContentAsString());
        return UUID.fromString(body.get("id").asText());
    }

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

    @Test
    void getConnectorByIdReturns200ForExistingConnector() throws Exception {
        UUID connectorId = seedConnector("dingtalk-bot-get");
        mockMvc.perform(get("/api/v1/connectors/{id}", connectorId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(connectorId.toString()))
                .andExpect(jsonPath("$.status").value("CONNECTED"));
    }

    @Test
    void getConnectorByIdReturns404ForUnknownId() throws Exception {
        mockMvc.perform(get("/api/v1/connectors/{id}", UUID.randomUUID()))
                .andExpect(status().isNotFound());
    }

    @Test
    void updateConfigReturns200ForExistingConnector() throws Exception {
        UUID connectorId = seedConnector("feishu-bot-update");
        mockMvc.perform(put("/api/v1/connectors/{id}/config", connectorId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"config\":\"{\\\"webhook_url\\\":\\\"https://new.example.com\\\"}\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(connectorId.toString()))
                .andExpect(jsonPath("$.status").value("CONNECTED"));
    }

    @Test
    void updateConfigReturns404ForUnknownConnector() throws Exception {
        mockMvc.perform(put("/api/v1/connectors/{id}/config", UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"config\":\"{}\"}"))
                .andExpect(status().isNotFound());
    }

    @Test
    void deleteConnectorReturns204AndSubsequentGet404() throws Exception {
        UUID connectorId = seedConnector("dingtalk-bot-delete");
        mockMvc.perform(delete("/api/v1/connectors/{id}", connectorId))
                .andExpect(status().isNoContent());
        mockMvc.perform(get("/api/v1/connectors/{id}", connectorId))
                .andExpect(status().isNotFound());
    }

    @Test
    void deleteConnectorReturns404ForUnknownId() throws Exception {
        mockMvc.perform(delete("/api/v1/connectors/{id}", UUID.randomUUID()))
                .andExpect(status().isNotFound());
    }

    @Test
    void pingConnectorReturnsLatencyResultForExistingConnector() throws Exception {
        UUID connectorId = seedConnector("feishu-bot-ping");
        mockMvc.perform(post("/api/v1/connectors/{id}/ping", connectorId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").exists())
                .andExpect(jsonPath("$.latencyMs").isNumber());
    }

    @Test
    void pingConnectorReturns404ForUnknownId() throws Exception {
        mockMvc.perform(post("/api/v1/connectors/{id}/ping", UUID.randomUUID()))
                .andExpect(status().isNotFound());
    }
}
