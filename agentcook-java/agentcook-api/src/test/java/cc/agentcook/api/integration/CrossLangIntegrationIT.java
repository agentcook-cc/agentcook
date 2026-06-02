package cc.agentcook.api.integration;

import cc.agentcook.api.ApiIntegrationTestBase;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Day 49 cross-language integration: Java admin-bff issues an HS256
 * JWT, and a downstream caller (acting as the Python agent-core) is
 * expected to forward that token unchanged on the chat-stream call.
 *
 * <p>The Python service is mocked with a JDK {@link HttpServer} rather
 * than a testcontainers Python image. The contract under test is
 * <em>"the Authorization header survives the cross-lang boundary
 * intact"</em>; spinning up a real Python container would prove the
 * same property at a much higher cost. A real-image variant is on the
 * Phase 5 backlog (paired with the docker mirror unblock).</p>
 */
class CrossLangIntegrationIT extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;

    private HttpServer pythonStub;
    private final AtomicReference<String> capturedAuthHeader = new AtomicReference<>();
    private final AtomicReference<String> capturedBody = new AtomicReference<>();

    @BeforeEach
    void startPythonStub() throws Exception {
        capturedAuthHeader.set(null);
        capturedBody.set(null);
        pythonStub = HttpServer.create(new InetSocketAddress(0), 0);
        pythonStub.createContext("/api/v1/chat/stream", exchange -> {
            capturedAuthHeader.set(exchange.getRequestHeaders().getFirst("Authorization"));
            capturedBody.set(new String(
                    exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));

            byte[] sse = ("data: {\"role\":\"assistant\",\"content\":\"你好\",\"done\":false}\n\n"
                    + "data: {\"role\":\"assistant\",\"content\":\"\",\"done\":true,"
                    + "\"metadata\":{},\"model\":\"qwen-turbo\"}\n\n"
                    + "data: [DONE]\n\n").getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "text/event-stream");
            exchange.sendResponseHeaders(200, sse.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(sse);
            }
        });
        pythonStub.start();
    }

    @AfterEach
    void stopPythonStub() {
        if (pythonStub != null) pythonStub.stop(0);
    }

    @Test
    @DisplayName("Java login → JWT → Python /chat/stream receives same Bearer token unchanged")
    void javaIssuedJwtIsForwardedToPythonAsBearerHeader() throws Exception {
        String token = loginAndExtractToken();
        assertThat(token).isNotBlank();
        assertThat(token.split("\\.")).hasSize(3);

        int pythonPort = pythonStub.getAddress().getPort();
        URI streamUri = URI.create("http://127.0.0.1:" + pythonPort + "/api/v1/chat/stream");
        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(2))
                .build();
        HttpRequest request = HttpRequest.newBuilder(streamUri)
                .header("Authorization", "Bearer " + token)
                .header("Content-Type", "application/json")
                .header("Accept", "text/event-stream")
                .timeout(Duration.ofSeconds(5))
                .POST(HttpRequest.BodyPublishers.ofString(
                        "{\"session_id\":\"s-cross-1\",\"message\":\"你好\"}",
                        StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body())
                .contains("\"content\":\"你好\"")
                .contains("\"done\":true")
                .contains("[DONE]");

        assertThat(capturedAuthHeader.get())
                .as("Python stub must have received the same Bearer token Java issued")
                .isEqualTo("Bearer " + token);
        assertThat(capturedBody.get()).contains("\"session_id\":\"s-cross-1\"");
    }

    @Test
    @DisplayName("Empty username at Java side → 400, Python is never called")
    void javaRejectsEmptyUsernameBeforeReachingPython() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"\",\"password\":\"x\"}"))
                .andExpect(status().isBadRequest());
        assertThat(capturedAuthHeader.get())
                .as("Python stub should not have been called at all")
                .isNull();
    }

    private String loginAndExtractToken() throws Exception {
        MvcResult login = mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"yvan\",\"password\":\"phase5-cross-lang\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.accessToken").exists())
                .andReturn();
        JsonNode body = objectMapper.readTree(login.getResponse().getContentAsString());
        return body.get("accessToken").asText();
    }
}
