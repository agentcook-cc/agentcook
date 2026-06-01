package cc.agentcook.application.port.in;

import java.util.Objects;

public record ListPermissionsByUserQuery(String userId) {

    public ListPermissionsByUserQuery {
        Objects.requireNonNull(userId, "userId must not be null");
    }
}
