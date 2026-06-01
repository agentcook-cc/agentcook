package cc.agentcook.api.contract;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;

import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Day 24 contract scaffolding for the Java provider side. Validates
 * three things needed for the Day 25 broker handshake:
 * <ul>
 *   <li>the consumer-shape pact JSON is readable and well-formed,</li>
 *   <li>the {@code "one published plugin exists"} provider state is
 *       reproducible against the real persistence stack,</li>
 *   <li>the actual {@code GET /api/v1/plugins} response shape matches
 *       what the consumer pact declares.</li>
 * </ul>
 *
 * <p>Full pact-jvm provider verification ({@code @Provider /
 * @PactBroker}) lands Day 25 once Agent C wires the broker publish
 * flow — at that point this scaffolding test is replaced by a real
 * {@code @TestTemplate} verification driven by broker-fetched pacts.
 * The hand-written JSON under {@code src/test/resources/pacts/} stays
 * as a contract template and consumer reference.</p>
 */
class ContractScaffoldingTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private PluginRepository pluginRepository;

    @Test
    void pactJsonTemplateIsValidAndDeclaresExpectedInteraction() throws Exception {
        try (InputStream is = getClass().getResourceAsStream("/pacts/agentcook-app-agentcook-java.json")) {
            assertNotNull(is, "Pact JSON template must ship under classpath:pacts/");
            JsonNode pact = new ObjectMapper().readTree(is);

            assertEquals("agentcook-app", pact.path("consumer").path("name").asText());
            assertEquals("agentcook-java", pact.path("provider").path("name").asText());

            JsonNode interaction = pact.path("interactions").get(0);
            assertEquals("list published plugins", interaction.path("description").asText());
            assertEquals("GET", interaction.path("request").path("method").asText());
            assertEquals("/api/v1/plugins", interaction.path("request").path("path").asText());
            assertEquals(200, interaction.path("response").path("status").asInt());
        }
    }

    @Test
    void providerStateOnePublishedPluginExistsIsReproducibleAndMatchesContract() throws Exception {
        // Provider state setup mirroring the Day 25 @State("one published plugin exists") method.
        Plugin plugin = Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, "test plugin");
        plugin.publish();
        pluginRepository.save(plugin);

        // Verify the live endpoint shape matches what the pact JSON expects.
        mockMvc.perform(get("/api/v1/plugins"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].name").value("dingtalk-bot"))
                .andExpect(jsonPath("$[0].version").value("1.0.0"))
                .andExpect(jsonPath("$[0].kind").value("WEBHOOK"))
                .andExpect(jsonPath("$[0].status").value("PUBLISHED"))
                .andExpect(jsonPath("$[0].id").exists())
                .andExpect(jsonPath("$[0].createdAt").exists())
                .andExpect(jsonPath("$[0].updatedAt").exists());

        // UUID format check on id (matches the pact's matcher).
        var result = mockMvc.perform(get("/api/v1/plugins")).andReturn();
        String body = result.getResponse().getContentAsString();
        assertTrue(body.matches(".*[0-9a-fA-F-]{36}.*"), "id must be UUID-shaped per pact matcher");
    }
}
