package cc.agentcook.infrastructure.registry;

import io.etcd.jetcd.ByteSequence;
import io.etcd.jetcd.Client;
import io.etcd.jetcd.KV;
import io.etcd.jetcd.Lease;
import io.etcd.jetcd.kv.GetResponse;
import io.etcd.jetcd.lease.LeaseGrantResponse;
import io.etcd.jetcd.options.GetOption;
import io.etcd.jetcd.options.PutOption;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * etcd-based service registry for microservice discovery.
 * Key format: /agentcook/services/{serviceName}/{instanceId}
 * Value: JSON {"host":"...","port":8080}
 *
 * <p>Uses a 30s lease with scheduled keepAlive renewal every 10s.</p>
 */
public class EtcdServiceRegistry {

    private static final Logger log = LoggerFactory.getLogger(EtcdServiceRegistry.class);
    private static final String KEY_PREFIX = "/agentcook/services/";
    private static final long LEASE_TTL_SECONDS = 30;
    private static final long RENEW_INTERVAL_SECONDS = 10;

    private final Client etcdClient;
    private long leaseId;
    private final ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread thread = new Thread(r, "etcd-lease-renew");
        thread.setDaemon(true);
        return thread;
    });

    public EtcdServiceRegistry(String etcdEndpoint) {
        this.etcdClient = Client.builder()
                .endpoints(etcdEndpoint)
                .build();
    }

    public EtcdServiceRegistry(Client etcdClient) {
        this.etcdClient = etcdClient;
    }

    /**
     * Register a service instance with a 30s TTL lease + periodic renewal.
     */
    public void register(String serviceName, String instanceId, String host, int port) {
        try {
            Lease leaseClient = etcdClient.getLeaseClient();
            LeaseGrantResponse leaseGrant = leaseClient.grant(LEASE_TTL_SECONDS).get(5, TimeUnit.SECONDS);
            this.leaseId = leaseGrant.getID();

            String key = KEY_PREFIX + serviceName + "/" + instanceId;
            String value = "{\"host\":\"" + host + "\",\"port\":" + port + "}";

            KV kvClient = etcdClient.getKVClient();
            kvClient.put(
                    ByteSequence.from(key, StandardCharsets.UTF_8),
                    ByteSequence.from(value, StandardCharsets.UTF_8),
                    PutOption.newBuilder().withLeaseId(leaseId).build()
            ).get(5, TimeUnit.SECONDS);

            // Schedule periodic lease renewal
            scheduler.scheduleAtFixedRate(() -> {
                try {
                    leaseClient.keepAliveOnce(leaseId).get(5, TimeUnit.SECONDS);
                } catch (Exception e) {
                    log.warn("Lease renewal failed for lease={}", leaseId, e);
                }
            }, RENEW_INTERVAL_SECONDS, RENEW_INTERVAL_SECONDS, TimeUnit.SECONDS);

            log.info("Registered service: {} -> {}:{} (lease={})", key, host, port, leaseId);
        } catch (Exception e) {
            log.error("Failed to register service {}/{}", serviceName, instanceId, e);
        }
    }

    /**
     * Discover all instances of a service by prefix scan.
     */
    public List<ServiceInstance> discover(String serviceName) {
        try {
            String prefix = KEY_PREFIX + serviceName + "/";
            KV kvClient = etcdClient.getKVClient();
            GetResponse response = kvClient.get(
                    ByteSequence.from(prefix, StandardCharsets.UTF_8),
                    GetOption.newBuilder().isPrefix(true).build()
            ).get(5, TimeUnit.SECONDS);

            return response.getKvs().stream()
                    .map(kv -> parseServiceInstance(kv.getValue().toString(StandardCharsets.UTF_8)))
                    .collect(Collectors.toList());
        } catch (Exception e) {
            log.error("Failed to discover service {}", serviceName, e);
            return List.of();
        }
    }

    /**
     * Deregister by revoking the lease (all keys bound to this lease are removed).
     */
    public void deregister() {
        scheduler.shutdownNow();
        if (leaseId > 0) {
            try {
                etcdClient.getLeaseClient().revoke(leaseId).get(5, TimeUnit.SECONDS);
                log.info("Deregistered service (lease={})", leaseId);
            } catch (Exception e) {
                log.warn("Failed to deregister (lease={})", leaseId, e);
            }
        }
    }

    public void close() {
        deregister();
        etcdClient.close();
    }

    private ServiceInstance parseServiceInstance(String json) {
        String host = extractField(json, "host");
        int port = Integer.parseInt(extractField(json, "port"));
        return new ServiceInstance(host, port);
    }

    private static String extractField(String json, String field) {
        String key = "\"" + field + "\":";
        int idx = json.indexOf(key);
        if (idx < 0) return "";
        int start = idx + key.length();
        if (json.charAt(start) == '"') {
            start++;
            int end = json.indexOf("\"", start);
            return json.substring(start, end);
        }
        int end = start;
        while (end < json.length() && (Character.isDigit(json.charAt(end)) || json.charAt(end) == '.')) {
            end++;
        }
        return json.substring(start, end);
    }
}
