package cc.agentcook.application.port.in;

import java.util.Objects;

public record ListConnectorsQuery(String pluginId) {

    public ListConnectorsQuery {
        Objects.requireNonNull(pluginId, "pluginId must not be null");
    }
}
