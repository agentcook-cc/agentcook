package cc.agentcook.application.port.in;

import java.util.Objects;

/**
 * Record one completed chat turn against the caller's free-tier quota.
 *
 * @param userId the caller's user id (JWT subject)
 */
public record ConsumeQuotaCommand(String userId) {

    public ConsumeQuotaCommand {
        Objects.requireNonNull(userId, "userId must not be null");
    }
}
