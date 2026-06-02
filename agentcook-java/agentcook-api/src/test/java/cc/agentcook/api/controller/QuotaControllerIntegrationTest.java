package cc.agentcook.api.controller;

import cc.agentcook.api.AgentcookJavaApplication;
import cc.agentcook.api.auth.JwtTokenIssuer;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaConnectorRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaPermissionRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaPluginRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaSessionRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaUserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;

import java.util.UUID;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Unlike the other *ControllerIntegrationTest classes, this one does NOT
 * extend {@code ApiIntegrationTestBase}: that base imports the
 * permitAll-style {@code TestSecurityConfig}, which short-circuits the
 * Bearer-token resource-server chain and leaves {@code
 * @AuthenticationPrincipal Jwt} null inside the controller — the very
 * principal this endpoint needs to read.
 *
 * <p>So this test boots the full app against Testcontainers postgres,
 * uses the production {@code SecurityConfig} (HS256 JWT resource
 * server) and mints real tokens via {@link JwtTokenIssuer}. The
 * dev-mode invariant exploited here is that any UUID-shaped string
 * is acceptable as a login subject — so a token whose sub is the
 * just-saved user's id maps cleanly back to a row.</p>
 */
@SpringBootTest(
        classes = AgentcookJavaApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT
)
@AutoConfigureMockMvc
@ActiveProfiles("test")
class QuotaControllerIntegrationTest {

    /** JVM-wide singleton — same instance as the other IT classes share. */
    @ServiceConnection
    @SuppressWarnings("resource")
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("agentcook_business")
            .withUsername("test")
            .withPassword("test")
            .withUrlParam("sslmode", "disable");

    static {
        POSTGRES.start();
    }

    @Autowired private MockMvc mockMvc;
    @Autowired private UserRepository userRepository;
    @Autowired private JwtTokenIssuer tokenIssuer;

    @Autowired private JpaPermissionRepository permissionsForCleanup;
    @Autowired private JpaConnectorRepository connectorsForCleanup;
    @Autowired private JpaSessionRepository sessionsForCleanup;
    @Autowired private JpaPluginRepository pluginsForCleanup;
    @Autowired private JpaUserRepository usersForCleanup;

    @BeforeEach
    void wipeAllTables() {
        // FK order: permissions / connectors / sessions reference users
        // and plugins; clear children before parents to keep V2 seed
        // data from re-tripping the cascade.
        permissionsForCleanup.deleteAll();
        connectorsForCleanup.deleteAll();
        sessionsForCleanup.deleteAll();
        pluginsForCleanup.deleteAll();
        usersForCleanup.deleteAll();
    }

    @Test
    void getQuota_freshUser_returnsV1DefaultQuota() throws Exception {
        User user = userRepository.save(User.create("quota1@example.com", "Q1"));
        String token = tokenIssuer.issue(user.getId().value().toString());

        mockMvc.perform(get("/api/v1/quota").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userId").value(user.getId().value().toString()))
                .andExpect(jsonPath("$.used").value(0))
                .andExpect(jsonPath("$.quota").value(User.DEFAULT_FREE_QUOTA))
                .andExpect(jsonPath("$.remaining").value(User.DEFAULT_FREE_QUOTA));
    }

    @Test
    void getQuota_afterOneConsumption_reflectsUsedCount() throws Exception {
        User user = User.create("quota2@example.com", "Q2");
        user.consumeFreeQuestion();
        userRepository.save(user);
        String token = tokenIssuer.issue(user.getId().value().toString());

        mockMvc.perform(get("/api/v1/quota").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.used").value(1))
                .andExpect(jsonPath("$.remaining").value(User.DEFAULT_FREE_QUOTA - 1));
    }

    @Test
    void getQuota_quotaExhausted_remainingIsZero() throws Exception {
        User user = User.create("quota3@example.com", "Q3");
        for (int i = 0; i < User.DEFAULT_FREE_QUOTA; i++) {
            user.consumeFreeQuestion();
        }
        userRepository.save(user);
        String token = tokenIssuer.issue(user.getId().value().toString());

        mockMvc.perform(get("/api/v1/quota").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.used").value(User.DEFAULT_FREE_QUOTA))
                .andExpect(jsonPath("$.remaining").value(0));
    }

    @Test
    void getQuota_withoutToken_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/quota"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getQuota_subjectNotInDatabase_returns404() throws Exception {
        // A valid token whose sub points at a UUID that no user row
        // exists for. Phase 3 dev login mints these freely; the
        // controller must surface a 404 rather than a 500.
        String token = tokenIssuer.issue(UUID.randomUUID().toString());

        mockMvc.perform(get("/api/v1/quota").header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }

    @Test
    void getQuota_subjectNotAUuid_returns404() throws Exception {
        // Phase 3 dev login allows arbitrary usernames as sub — anything
        // that's not parseable as a UUID can't map to a User row and
        // must return 404, not 500.
        String token = tokenIssuer.issue("not-a-uuid");

        mockMvc.perform(get("/api/v1/quota").header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }
}
