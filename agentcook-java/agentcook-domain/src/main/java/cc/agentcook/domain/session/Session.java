package cc.agentcook.domain.session;

import cc.agentcook.domain.session.event.SessionCreatedEvent;
import cc.agentcook.domain.user.UserId;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Session Aggregate Root.
 * Represents a conversation session between a user and an agent.
 */
public class Session {

    private final SessionId id;
    private final UserId userId;
    private String title;
    private SessionStatus status;
    private final Instant createdAt;
    private Instant updatedAt;

    private final List<Object> domainEvents = new ArrayList<>();

    private Session(SessionId id, UserId userId, String title, SessionStatus status, Instant createdAt, Instant updatedAt) {
        this.id = Objects.requireNonNull(id, "id must not be null");
        this.userId = Objects.requireNonNull(userId, "userId must not be null");
        this.title = title;
        this.status = Objects.requireNonNull(status, "status must not be null");
        this.createdAt = Objects.requireNonNull(createdAt, "createdAt must not be null");
        this.updatedAt = Objects.requireNonNull(updatedAt, "updatedAt must not be null");
    }

    /**
     * Factory: create a new Session (raises SessionCreatedEvent).
     */
    public static Session create(UserId userId, String title) {
        if (userId == null) throw new IllegalArgumentException("userId must not be null");
        SessionId id = SessionId.generate();
        Instant now = Instant.now();
        Session session = new Session(id, userId, title, SessionStatus.ACTIVE, now, now);
        session.domainEvents.add(new SessionCreatedEvent(id, userId, title, now));
        return session;
    }

    /**
     * Reconstitute from persistence (no events raised).
     */
    public static Session reconstitute(SessionId id, UserId userId, String title, SessionStatus status, Instant createdAt, Instant updatedAt) {
        return new Session(id, userId, title, status, createdAt, updatedAt);
    }

    public void archive() {
        if (this.status == SessionStatus.DELETED) {
            throw new IllegalStateException("Cannot archive a deleted session");
        }
        this.status = SessionStatus.ARCHIVED;
        this.updatedAt = Instant.now();
    }

    public void activate() {
        if (this.status == SessionStatus.DELETED) {
            throw new IllegalStateException("Cannot activate a deleted session");
        }
        this.status = SessionStatus.ACTIVE;
        this.updatedAt = Instant.now();
    }

    public void markDeleted() {
        this.status = SessionStatus.DELETED;
        this.updatedAt = Instant.now();
    }

    public void updateTitle(String title) {
        this.title = title;
        this.updatedAt = Instant.now();
    }

    // --- Getters ---

    public SessionId getId() { return id; }
    public UserId getUserId() { return userId; }
    public String getTitle() { return title; }
    public SessionStatus getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public List<Object> getDomainEvents() {
        return Collections.unmodifiableList(domainEvents);
    }

    public void clearDomainEvents() {
        domainEvents.clear();
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (other == null || getClass() != other.getClass()) return false;
        Session session = (Session) other;
        return id.equals(session.id);
    }

    @Override
    public int hashCode() {
        return id.hashCode();
    }

    @Override
    public String toString() {
        return "Session{id=" + id + ", userId=" + userId + ", status=" + status + "}";
    }
}
