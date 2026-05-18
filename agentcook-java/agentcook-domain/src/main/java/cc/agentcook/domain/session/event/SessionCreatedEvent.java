package cc.agentcook.domain.session.event;

import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.user.UserId;

import java.time.Instant;

/**
 * Domain Event raised when a new Session is created.
 */
public record SessionCreatedEvent(
        SessionId sessionId,
        UserId userId,
        String title,
        Instant occurredAt
) {
    public SessionCreatedEvent {
        if (sessionId == null) throw new IllegalArgumentException("sessionId must not be null");
        if (userId == null) throw new IllegalArgumentException("userId must not be null");
        if (occurredAt == null) occurredAt = Instant.now();
    }

    public SessionCreatedEvent(SessionId sessionId, UserId userId, String title) {
        this(sessionId, userId, title, Instant.now());
    }
}
