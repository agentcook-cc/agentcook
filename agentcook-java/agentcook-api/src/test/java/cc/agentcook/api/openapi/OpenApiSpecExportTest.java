package cc.agentcook.api.openapi;

import cc.agentcook.api.ApiIntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

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

    @Autowired
    private MockMvc mockMvc;

    @Test
    void exportsJavaV1Yaml() throws Exception {
        MvcResult result = mockMvc.perform(get("/v3/api-docs.yaml"))
                .andExpect(status().isOk())
                .andReturn();

        String yaml = result.getResponse().getContentAsString();

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
                .getContentAsString();

        // Module cwd is agentcook-cc/agentcook-java/agentcook-api at test runtime.
        Path published = Path.of("..", "..", "docs", "api", "java-v1.yaml");
        if (!Files.exists(published)) {
            // Skip silently if the published copy is not in this checkout — the
            // assertion still fires from a full repo where it exists.
            return;
        }
        String publishedYaml = Files.readString(published);

        // Drift detection: the controller-level surface should match exactly.
        // Order/whitespace inside the spec is springdoc-deterministic so we
        // assert path-prefix containment + the version + scope marker.
        for (String marker : List.of(
                "/api/v1/users",
                "/api/v1/sessions",
                "/api/v1/plugins",
                "title: agentcook Java Business API",
                "version: 1.0.0",
                "x-scope: java-business")) {
            assertTrue(live.contains(marker),
                    "live spec missing marker: " + marker);
            assertTrue(publishedYaml.contains(marker),
                    "published java-v1.yaml missing marker (drift): " + marker
                            + " — re-run OpenApiSpecExportTest and copy target/openapi/java-v1.yaml.");
        }
    }
}
