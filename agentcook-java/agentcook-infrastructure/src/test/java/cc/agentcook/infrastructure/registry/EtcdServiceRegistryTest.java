package cc.agentcook.infrastructure.registry;

import io.etcd.jetcd.ByteSequence;
import io.etcd.jetcd.Client;
import io.etcd.jetcd.kv.GetResponse;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration test for EtcdServiceRegistry using Testcontainers.
 * Tagged "etcd" — excluded from default mvn test to avoid image-pull timeout
 * in environments without a fast Docker mirror.
 * Run explicitly: mvn test -Dgroups=etcd
 */
@Testcontainers
@Tag("etcd")
class EtcdServiceRegistryTest {

    @Container
    static final GenericContainer<?> ETCD = new GenericContainer<>(DockerImageName.parse("bitnami/etcd:3.5"))
            .withExposedPorts(2379)
            .withEnv("ALLOW_NONE_AUTHENTICATION", "yes")
            .withEnv("ETCD_ADVERTISE_CLIENT_URLS", "http://0.0.0.0:2379");

    private EtcdServiceRegistry registry;
    private Client verifyClient;

    @BeforeEach
    void setUp() {
        String endpoint = "http://localhost:" + ETCD.getMappedPort(2379);
        registry = new EtcdServiceRegistry(endpoint);
        verifyClient = Client.builder().endpoints(endpoint).build();
    }

    @AfterEach
    void tearDown() {
        if (registry != null) registry.close();
        if (verifyClient != null) verifyClient.close();
    }

    @Test
    void registerAndDiscover() {
        registry.register("admin-bff", "inst-1", "10.0.0.1", 8080);

        List<ServiceInstance> instances = registry.discover("admin-bff");
        assertEquals(1, instances.size());
        assertEquals("10.0.0.1", instances.get(0).host());
        assertEquals(8080, instances.get(0).port());
    }

    @Test
    void discoverReturnsEmptyWhenNoInstances() {
        List<ServiceInstance> instances = registry.discover("nonexistent-service");
        assertTrue(instances.isEmpty());
    }

    @Test
    void deregisterRemovesKey() throws Exception {
        registry.register("admin-bff", "inst-2", "10.0.0.2", 8080);

        List<ServiceInstance> before = registry.discover("admin-bff");
        assertFalse(before.isEmpty());

        registry.deregister();
        Thread.sleep(200);

        GetResponse response = verifyClient.getKVClient().get(
                ByteSequence.from("/agentcook/services/admin-bff/inst-2", StandardCharsets.UTF_8)
        ).get(5, TimeUnit.SECONDS);
        assertEquals(0, response.getCount());
    }
}
