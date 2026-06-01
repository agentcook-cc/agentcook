package cc.agentcook.api.security;

import cc.agentcook.api.auth.JwtTokenIssuer;
import cc.agentcook.api.config.SecurityConfig;
import cc.agentcook.api.controller.AuthController;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Verifies the real production {@link SecurityConfig} (OAuth2 Resource
 * Server + HS256 JWT) WITHOUT Testcontainers / database. Boots a
 * minimal Spring context with only security + auth controller.
 *
 * <p>Does NOT activate the {@code test} profile — the production
 * {@code SecurityConfig} is the one under test, not the permitAll
 * {@code TestSecurityConfig}.</p>
 */
@SpringBootTest(
        classes = SecurityChainTest.MinimalSecurityApp.class,
        webEnvironment = SpringBootTest.WebEnvironment.MOCK,
        properties = {
                "agentcook.auth.jwt-secret=test-secret-must-be-at-least-32-bytes!!",
                "agentcook.auth.jwt-ttl-seconds=3600"
        }
)
@AutoConfigureMockMvc
class SecurityChainTest {

    /**
     * Minimal Spring Boot app that loads ONLY security + auth controller.
     * No JPA, no Flyway, no Redis, no Testcontainers.
     */
    @Configuration
    @Import({SecurityConfig.class, JwtTokenIssuer.class, AuthController.class})
    @org.springframework.boot.autoconfigure.SpringBootApplication(
            exclude = {
                    org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration.class,
                    org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration.class,
                    org.springframework.boot.autoconfigure.data.jpa.JpaRepositoriesAutoConfiguration.class,
                    org.springframework.boot.autoconfigure.flyway.FlywayAutoConfiguration.class,
                    org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration.class,
                    org.springframework.boot.autoconfigure.data.redis.RedisRepositoriesAutoConfiguration.class
            },
            scanBasePackages = "cc.agentcook.api.security" // scan nothing extra
    )
    static class MinimalSecurityApp {
    }

    @Autowired private MockMvc mockMvc;
    @Autowired private JwtTokenIssuer tokenIssuer;

    @Test
    void protectedEndpoint_withoutToken_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/users"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void protectedEndpoint_withValidToken_passesSecurityChain() throws Exception {
        String token = tokenIssuer.issue("alice");
        // /api/v1/users is not mapped (only AuthController loaded),
        // so 404 — but NOT 401/403: security chain passed.
        mockMvc.perform(get("/api/v1/users")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
    }

    @Test
    void protectedEndpoint_withInvalidToken_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/users")
                        .header("Authorization", "Bearer invalid.jwt.token"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void loginEndpoint_isPublic_andReturnsJwt() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":"dev"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").value(notNullValue()))
                .andExpect(jsonPath("$.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.expiresIn").value(3600));
    }

    @Test
    void loginEndpoint_rejectsBlankPassword() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":""}
                                """))
                .andExpect(status().isBadRequest());
    }
}
