package cc.agentcook.domain.user.event;

import cc.agentcook.domain.user.UserId;

import java.time.Instant;

/**
 * Domain Event raised when a new User is created.
 */
public record UserCreatedEvent(
        UserId userId,
        String email,
        Instant occurredAt
) {
    public UserCreatedEvent {
        if (userId == null) throw new IllegalArgumentException("userId must not be null");
        if (email == null || email.isBlank()) throw new IllegalArgumentException("email must not be blank");
        if (occurredAt == null) occurredAt = Instant.now();
    }

    public UserCreatedEvent(UserId userId, String email) {
        this(userId, email, Instant.now());
    }
}
