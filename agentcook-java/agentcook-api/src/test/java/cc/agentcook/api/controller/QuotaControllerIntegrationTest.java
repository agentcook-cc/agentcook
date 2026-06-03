package cc.agentcook.api.controller;

import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Quota endpoint integration test. Buffer Day 66 redesign: extends
 * {@link ApiIntegrationTestBase} (shared JVM-wide Testcontainers
 * postgres) — the Day 56 "independent base" approach booted a second
 * {@code @ServiceConnection PostgreSQLContainer} singleton inside the
 * same JVM, which on colima's ~2 GiB memory budget meant one of the
 * two PG containers lost the start race and the test surfaced as
 * "connection refused localhost:NNN" on every run (host docker
 * boundary forbids cleaning up colima resources).
 *
 * <p>The Day 56 reason for the independent base was that the base's
 * permitAll {@code TestSecurityConfig} short-circuits the Bearer
 * resource-server chain and leaves {@code @AuthenticationPrincipal
 * Jwt} as null inside {@link QuotaController}. The Day 66 fix uses
 * Spring Security's {@code MockMvcRequestPostProcessors.jwt()} to
 * inject a {@link org.springframework.security.oauth2.jwt.Jwt}
 * principal at the request level — bypassing the
 * SecurityFilterChain entirely so we don't need the production chain
 * active, and gaining direct control over the sub claim per test.</p>
 *
 * <p>The 6 boundary cases below are unchanged in intent (fresh /
 * used / exhausted / no-auth / sub-unknown-user / sub-not-a-uuid);
 * only the way we present the principal to the controller changes.</p>
 */
class QuotaControllerIntegrationTest extends ApiIntegrationTestBase {

    @Autowired private MockMvc mockMvc;
    @Autowired private UserRepository userRepository;

    @org.springframework.beans.factory.annotation.Autowired
    private cc.agentcook.infrastructure.persistence.jpa.JpaPermissionRepository permissionsForCleanup;
    @org.springframework.beans.factory.annotation.Autowired
    private cc.agentcook.infrastructure.persistence.jpa.JpaConnectorRepository connectorsForCleanup;
    @org.springframework.beans.factory.annotation.Autowired
    private cc.agentcook.infrastructure.persistence.jpa.JpaSessionRepository sessionsForCleanup;
    @org.springframework.beans.factory.annotation.Autowired
    private cc.agentcook.infrastructure.persistence.jpa.JpaPluginRepository pluginsForCleanup;
    @org.springframework.beans.factory.annotation.Autowired
    private cc.agentcook.infrastructure.persistence.jpa.JpaUserRepository usersForCleanup;

    @org.junit.jupiter.api.BeforeEach
    void wipeQuotaTables() {
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
        String sub = user.getId().value().toString();

        mockMvc.perform(get("/api/v1/quota")
                        .with(jwt().jwt(b -> b.subject(sub))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userId").value(sub))
                .andExpect(jsonPath("$.used").value(0))
                .andExpect(jsonPath("$.quota").value(User.DEFAULT_FREE_QUOTA))
                .andExpect(jsonPath("$.remaining").value(User.DEFAULT_FREE_QUOTA));
    }

    @Test
    void getQuota_afterOneConsumption_reflectsUsedCount() throws Exception {
        User user = User.create("quota2@example.com", "Q2");
        user.consumeFreeQuestion();
        userRepository.save(user);
        String sub = user.getId().value().toString();

        mockMvc.perform(get("/api/v1/quota")
                        .with(jwt().jwt(b -> b.subject(sub))))
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
        String sub = user.getId().value().toString();

        mockMvc.perform(get("/api/v1/quota")
                        .with(jwt().jwt(b -> b.subject(sub))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.used").value(User.DEFAULT_FREE_QUOTA))
                .andExpect(jsonPath("$.remaining").value(0));
    }

    @Test
    void getQuota_withoutPrincipal_returns404UnderPermitAll() throws Exception {
        // Under the base's permitAll TestSecurityConfig, "no auth"
        // surfaces inside the controller as a null Jwt rather than as
        // a 401 from the filter chain. The controller treats null sub
        // the same way it treats an unparseable sub: 404 "no resolvable
        // user". Production (real SecurityConfig + bearer enforcement)
        // returns 401 at the filter — covered by the JWT boundary
        // tests in SecurityChainTest.
        mockMvc.perform(get("/api/v1/quota"))
                .andExpect(status().isNotFound());
    }

    @Test
    void getQuota_subjectNotInDatabase_returns404() throws Exception {
        String unknownUserId = UUID.randomUUID().toString();

        mockMvc.perform(get("/api/v1/quota")
                        .with(jwt().jwt(b -> b.subject(unknownUserId))))
                .andExpect(status().isNotFound());
    }

    @Test
    void getQuota_subjectNotAUuid_returns404() throws Exception {
        // Phase 3 dev login allows arbitrary usernames as sub — anything
        // that's not parseable as a UUID can't map to a User row and
        // must return 404, not 500.
        mockMvc.perform(get("/api/v1/quota")
                        .with(jwt().jwt(b -> b.subject("not-a-uuid"))))
                .andExpect(status().isNotFound());
    }
}
