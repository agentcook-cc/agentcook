package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class PluginControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private PluginRepository pluginRepository;

    @Test
    void listsOnlyPublishedPluginsByDefault() throws Exception {
        Plugin p1 = Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, "test");
        p1.publish();
        pluginRepository.save(p1);
        pluginRepository.save(Plugin.create("draft-bot", "0.1.0", PluginKind.HTTP, "draft"));

        mockMvc.perform(get("/api/v1/plugins"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].name").value("dingtalk-bot"))
                .andExpect(jsonPath("$[0].status").value("PUBLISHED"));
    }

    @Test
    void filtersByExplicitStatus() throws Exception {
        pluginRepository.save(Plugin.create("draft-bot", "0.1.0", PluginKind.HTTP, "draft"));

        mockMvc.perform(get("/api/v1/plugins").param("status", "DRAFT"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].status").value("DRAFT"));
    }

    @Test
    void uploadsValidZipAndReturns201() throws Exception {
        byte[] zip = zipWithManifest("""
                {"name":"upload-bot","version":"1.0.0","kind":"WEBHOOK","description":"upload demo"}
                """);
        MockMultipartFile file = new MockMultipartFile(
                "file", "upload-bot.zip", "application/zip", zip);

        mockMvc.perform(multipart("/api/v1/plugins").file(file))
                .andExpect(status().isCreated())
                .andExpect(header().exists("Location"))
                .andExpect(jsonPath("$.name").value("upload-bot"))
                .andExpect(jsonPath("$.version").value("1.0.0"))
                .andExpect(jsonPath("$.kind").value("WEBHOOK"))
                .andExpect(jsonPath("$.status").value("DRAFT"));
    }

    @Test
    void uploadingZipWithoutManifestReturns400() throws Exception {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        try (ZipOutputStream zos = new ZipOutputStream(buf)) {
            zos.putNextEntry(new ZipEntry("README.md"));
            zos.write("hi".getBytes());
            zos.closeEntry();
        }
        MockMultipartFile file = new MockMultipartFile(
                "file", "broken.zip", "application/zip", buf.toByteArray());

        mockMvc.perform(multipart("/api/v1/plugins").file(file))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_PLUGIN_PACKAGE"));
    }

    @Test
    void publishesDraftPlugin() throws Exception {
        Plugin draft = pluginRepository.save(Plugin.create("pub-test", "1.0.0", PluginKind.MCP, "publish test"));

        mockMvc.perform(put("/api/v1/plugins/" + draft.getId().value() + "/publish"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PUBLISHED"))
                .andExpect(jsonPath("$.name").value("pub-test"));
    }

    private static byte[] zipWithManifest(String manifestJson) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        try (ZipOutputStream zos = new ZipOutputStream(buf)) {
            zos.putNextEntry(new ZipEntry("plugin.json"));
            zos.write(manifestJson.getBytes());
            zos.closeEntry();
        }
        return buf.toByteArray();
    }
}
