package cc.agentcook.api.config;

import cc.agentcook.infrastructure.registry.EtcdServiceRegistry;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.UUID;

/**
 * Registers this Java service instance to etcd on startup
 * and deregisters on graceful shutdown.
 * Disabled by default in dev/test; enabled via etcd.enabled=true.
 */
@Configuration
@ConditionalOnProperty(name = "etcd.enabled", havingValue = "true", matchIfMissing = false)
public class ServiceRegistryConfig {

    private static final Logger log = LoggerFactory.getLogger(ServiceRegistryConfig.class);

    @Value("${etcd.endpoints:http://localhost:2379}")
    private String etcdEndpoints;

    @Value("${server.port:8080}")
    private int serverPort;

    @Value("${agentcook.service.name:admin-bff}")
    private String serviceName;

    @Value("${agentcook.service.host:${HOSTNAME:localhost}}")
    private String serviceHost;

    private final String instanceId = UUID.randomUUID().toString().substring(0, 8);
    private EtcdServiceRegistry registry;

    @PostConstruct
    public void registerToEtcd() {
        registry = new EtcdServiceRegistry(etcdEndpoints);
        registry.register(serviceName, instanceId, serviceHost, serverPort);
        log.info("Service registered to etcd: {}/{} -> {}:{}", serviceName, instanceId, serviceHost, serverPort);
    }

    @PreDestroy
    public void deregisterFromEtcd() {
        if (registry != null) {
            registry.close();
            log.info("Service deregistered from etcd: {}/{}", serviceName, instanceId);
        }
    }

    @Bean
    public EtcdServiceRegistry etcdServiceRegistry() {
        return registry;
    }
}
