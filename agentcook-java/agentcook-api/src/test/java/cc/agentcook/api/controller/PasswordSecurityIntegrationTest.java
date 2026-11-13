package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.user.UserRepository;
import cc.agentcook.domain.user.UserId;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;

import java.util.ArrayList;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/** Real resource-server chain, password hashing and PostgreSQL transactions. */
@TestPropertySource(properties = {"agentcook.auth.auto-provision=false", "agentcook.auth.admins=admin"})
class PasswordSecurityIntegrationTest extends ApiIntegrationTestBase {
    @Autowired private UserRepository users;
    @Autowired private ObjectMapper json;
    @Override protected boolean defaultAdmin() { return false; }

    private JsonNode register(String username) throws Exception {
        return json.readTree(mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(java.util.Map.of("username", username, "password", "password-123"))))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.refreshToken").isNotEmpty())
                .andReturn().getResponse().getContentAsString());
    }

    private String access(JsonNode tokens) { return "Bearer " + tokens.path("accessToken").asText(); }

    @Test
    void registerLoginRefreshAndTokenSeparation() throws Exception {
        JsonNode tokens = register("alice");
        mockMvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"alice\",\"password\":\"password-123\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.tokenType").value("Bearer"));
        JsonNode refreshed = json.readTree(mockMvc.perform(post("/api/v1/auth/refresh")
                .header("Authorization", "Bearer expired")
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(java.util.Map.of("refreshToken", tokens.path("refreshToken").asText()))))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        assertThat(refreshed.path("refreshToken").asText()).isNotEqualTo(tokens.path("refreshToken").asText());
        mockMvc.perform(get("/api/v1/users/me").header("Authorization", access(refreshed)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.email").value("alice@dev.local"));
        mockMvc.perform(get("/api/v1/users/me").header("Authorization", "Bearer " + tokens.path("refreshToken").asText()))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").isNotEmpty());
        mockMvc.perform(post("/api/v1/auth/refresh").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(java.util.Map.of("refreshToken", tokens.path("accessToken").asText()))))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value("AUTH_INVALID_REFRESH_TOKEN"));
        mockMvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"alice\",\"password\":\"password-123\"}"))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("AUTH_USER_EXISTS"));
    }

    @Test
    void wrongAndUnknownCredentialsHaveIdenticalErrorsAndDisabledAccountsAreForbidden() throws Exception {
        register("alice");
        String wrong = mockMvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"alice\",\"password\":\"wrong-password\"}"))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value("AUTH_INVALID_CREDENTIALS"))
                .andReturn().getResponse().getContentAsString();
        String unknown = mockMvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"unknown\",\"password\":\"wrong-password\"}"))
                .andExpect(status().isUnauthorized()).andReturn().getResponse().getContentAsString();
        assertThat(unknown).isEqualTo(wrong);
        var user = users.findByEmail("alice@dev.local").orElseThrow();
        user.suspend();
        users.save(user);
        mockMvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"alice\",\"password\":\"password-123\"}"))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.code").value("AUTH_ACCOUNT_DISABLED"));
    }

    @Test
    void roleAndSessionOwnershipAreEnforced() throws Exception {
        JsonNode alice = register("alice");
        JsonNode bob = register("bobby");
        JsonNode admin = register("admin");
        mockMvc.perform(get("/api/v1/users").header("Authorization", access(alice)))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.code").isNotEmpty());
        mockMvc.perform(get("/api/v1/users").header("Authorization", access(admin))).andExpect(status().isOk());
        JsonNode session = json.readTree(mockMvc.perform(post("/api/v1/sessions")
                .header("Authorization", access(alice)).contentType(MediaType.APPLICATION_JSON).content("{\"title\":\"Private\"}"))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString());
        String url = "/api/v1/sessions/" + session.path("id").asText();
        mockMvc.perform(get(url).header("Authorization", access(alice))).andExpect(status().isOk());
        mockMvc.perform(get(url).header("Authorization", access(bob)))
                .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("SESSION_NOT_FOUND"));
        mockMvc.perform(get(url).header("Authorization", access(admin))).andExpect(status().isOk());
    }

    @Test
    void concurrentConsumptionIsAtomicAndExhaustionDoesNotIncrement() throws Exception {
        JsonNode tokens = register("alice");
        String bearer = access(tokens);
        var user = users.findByEmail("alice@dev.local").orElseThrow();
        int quota = user.getFreeQuestionsQuota();
        var pool = Executors.newFixedThreadPool(8);
        try {
            var calls = new ArrayList<Callable<JsonNode>>();
            for (int i = 0; i < quota + 8; i++) calls.add(() -> json.readTree(mockMvc.perform(
                    post("/api/v1/quota/consume").header("Authorization", bearer))
                    .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()));
            int accepted = 0;
            for (var result : pool.invokeAll(calls)) if (!result.get().path("exhausted").asBoolean()) accepted++;
            assertThat(accepted).isEqualTo(quota);
            assertThat(users.findById(user.getId()).orElseThrow().getFreeQuestionsUsed()).isEqualTo(quota);
            mockMvc.perform(post("/api/v1/quota/consume").header("Authorization", bearer))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.remaining").value(0))
                    .andExpect(jsonPath("$.used").value(quota)).andExpect(jsonPath("$.exhausted").value(true));
        } finally {
            pool.shutdownNow();
            assertThat(pool.awaitTermination(10, TimeUnit.SECONDS)).isTrue();
        }
    }
}
