package cc.agentcook.infrastructure;

import cc.agentcook.infrastructure.persistence.jpa.JpaConnectorRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaPermissionRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaPluginRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaSessionRepository;
import cc.agentcook.infrastructure.persistence.jpa.JpaUserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ActiveProfiles;
import org.testcontainers.containers.PostgreSQLContainer;

/**
 * Shared SpringBoot + Testcontainers postgres harness.
 *
 * <p>The container is a {@code static} singleton — Testcontainers reuses
 * the same JVM-wide PostgreSQL instance across all subclasses, so the
 * fixture cost is paid once per Maven test run.</p>
 *
 * <p>Wiring uses {@code @ServiceConnection} (Spring Boot 3.1+) instead
 * of {@code @DynamicPropertySource}: the former binds the container's
 * connection details to Spring Boot's {@code DataSource} bean each
 * time the context is built, so a container that gets restarted between
 * IT classes never leaves Spring with a stale jdbc URL. The Day 27
 * flaky (~67% mvn failure rate, "Connection refused" against an old
 * port) is gone with this swap.</p>
 *
 * <p>Cleanup is centralized: subclasses do not declare their own
 * {@code @BeforeEach} cleanDb because deletion order has to honor the
 * FK chain (permissions / connectors / sessions before plugins / users).</p>
 */
@SpringBootTest(classes = TestApplication.class)
@ActiveProfiles("test")
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
public abstract class IntegrationTestBase {

    /**
     * JVM-wide singleton — started in the static block, lives until JVM
     * exit (Testcontainers' built-in shutdown hook stops it). We do NOT
     * use {@code @Testcontainers} + {@code @Container} because that
     * lifecycle stops the container after the first IT class's
     * {@code afterAll}, leaving subsequent IT classes pointing at a dead
     * port. {@code @ServiceConnection} re-binds the container's live
     * jdbc URL on every Spring context build, so context cache hits
     * never carry a stale URL forward.
     */
    @ServiceConnection
    @SuppressWarnings("resource")
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("agentcook_business")
            .withUsername("test")
            .withPassword("test")
            // postgres:16-alpine ships without SSL; the JDBC driver's default
            // sslmode tries SSL first and only falls back on a clean refusal,
            // so we pin sslmode=disable to skip the handshake entirely.
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
