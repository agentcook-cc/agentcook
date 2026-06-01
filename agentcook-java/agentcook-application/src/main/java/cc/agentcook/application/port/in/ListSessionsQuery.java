package cc.agentcook.application.port.in;

import java.util.Objects;

/**
 * Input Port query: list sessions for a given user.
 */
public record ListSessionsQuery(String userId) {

    public ListSessionsQuery {
        Objects.requireNonNull(userId, "userId must not be null");
    }
}
