package cc.agentcook.api.openapi;

import cc.agentcook.api.ApiIntegrationTestBase;
import com.fasterxml.jackson.dataformat.yaml.YAMLMapper;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MvcResult;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Boots the app, scrapes {@code /v3/api-docs.yaml} produced by
 * springdoc-openapi, and writes it to {@code target/openapi/java-v1.yaml}.
 *
 * <p>The author then copies that artifact to {@code docs/api/java-v1.yaml}
 * (cross-cutting flag) — keeping the build artifact and the published
 * spec separate so the test never reaches outside the module.</p>
 */
class OpenApiSpecExportTest extends ApiIntegrationTestBase {

    @Test
    void exportsJavaV1Yaml() throws Exception {
        MvcResult result = mockMvc.perform(get("/v3/api-docs.yaml"))
                .andExpect(status().isOk())
                .andReturn();

        String yaml = result.getResponse().getContentAsString(StandardCharsets.UTF_8);

        assertTrue(yaml.contains("/api/v1/users"), "spec must include UserController paths");
        assertTrue(yaml.contains("/api/v1/sessions"), "spec must include SessionController paths");
        assertTrue(yaml.contains("/api/v1/plugins"), "spec must include PluginController paths");
        assertTrue(yaml.contains("agentcook Java Business API"), "spec must carry our title");

        Path out = Path.of("target", "openapi", "java-v1.yaml");
        Files.createDirectories(out.getParent());
        Files.writeString(out, yaml);
    }

    @Test
    void liveSpecStaysInSyncWithPublishedFile() throws Exception {
        String live = mockMvc.perform(get("/v3/api-docs.yaml"))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString(StandardCharsets.UTF_8);

        Path published = Path.of("..", "..", "docs", "api", "java-v1.yaml");
        assertTrue(Files.isRegularFile(published), "published OpenAPI file is missing");
        // Compare the parsed documents because map ordering may differ between JVMs.
        var mapper = new YAMLMapper();
        assertEquals(mapper.readTree(live), mapper.readTree(Files.readString(published)),
                "Regenerate docs/api/java-v1.yaml from /v3/api-docs.yaml.");
    }
}
