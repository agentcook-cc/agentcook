package cc.agentcook.domain.user;

/**
 * Raised by {@link User#consumeFreeQuestion()} when a user has already
 * consumed their full free-tier quota (ADR-018 §2 step ②).
 *
 * <p>This is <em>not</em> an HTTP 4xx situation — the chat router /
 * Python middleware catches this and downgrades the request to
 * glm-4-flash instead of surfacing a quota error to the user. The
 * exception type just makes the boundary explicit.</p>
 */
public class QuotaExhaustedException extends RuntimeException {

    private final UserId userId;
    private final int quota;

    public QuotaExhaustedException(UserId userId, int quota) {
        super("Free-tier quota exhausted for user " + userId + " (quota=" + quota + ")");
        this.userId = userId;
        this.quota = quota;
    }

    public UserId getUserId() {
        return userId;
    }

    public int getQuota() {
        return quota;
    }
}
