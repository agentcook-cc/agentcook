package cc.agentcook.infrastructure.registry;

/**
 * Represents a discovered service instance from etcd.
 */
public record ServiceInstance(String host, int port) {

    public String toAddress() {
        return host + ":" + port;
    }
}
