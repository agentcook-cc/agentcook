package cc.agentcook.api;

import cc.agentcook.infrastructure.persistence.jpa.JpaConnectorRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaPermissionRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaPluginRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaSessionRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaUserRepository;
import cc.agentcook.api.config.TestSecurityConfig;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.testcontainers.containers.PostgreSQLContainer;

/**
 * Boots the full Spring Boot application against a Testcontainers
 * postgres. Redis autoconfig is excluded via {@code application-test.yml}'s
 * {@code spring.autoconfigure.exclude} (not via this base class) so the
 * full {@code @SpringBootApplication} component scan still reaches our
 * {@code SecurityConfig} — overriding {@code @EnableAutoConfiguration}
 * here was bypassing it and letting the default httpBasic chain return 401.
 *
 * <p>Wiring uses {@code @ServiceConnection} (Spring Boot 3.1+) instead
 * of {@code @DynamicPropertySource} to defeat the Day 27 flaky where
 * Spring Test Context cache held a stale jdbc URL after the postgres
 * container was restarted between IT classes.</p>
 */
@SpringBootTest(
        classes = AgentcookJavaApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT
)
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(TestSecurityConfig.class)
public abstract class ApiIntegrationTestBase {

    /** JVM-wide singleton — see IntegrationTestBase for rationale. */
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

    @Autowired private JpaPermissionRepository permissionsForCleanup;
    @Autowired private JpaConnectorRepository connectorsForCleanup;
    @Autowired private JpaSessionRepository sessionsForCleanup;
    @Autowired private JpaPluginRepository pluginsForCleanup;
    @Autowired private JpaUserRepository usersForCleanup;

    @BeforeEach
    void wipeAllTables() {
        permissionsForCleanup.deleteAll();
        connectorsForCleanup.deleteAll();
        sessionsForCleanup.deleteAll();
        pluginsForCleanup.deleteAll();
        usersForCleanup.deleteAll();
    }
}
