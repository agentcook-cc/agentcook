package cc.agentcook.domain.user;

import cc.agentcook.domain.user.event.UserCreatedEvent;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * User Aggregate Root.
 * Manages user identity, profile, and lifecycle state transitions.
 */
public class User {

    private final UserId id;
    private String email;
    private String nickname;
    private UserStatus status;
    private final Instant createdAt;
    private Instant updatedAt;

    private final List<Object> domainEvents = new ArrayList<>();

    private User(UserId id, String email, String nickname, UserStatus status, Instant createdAt, Instant updatedAt) {
        this.id = Objects.requireNonNull(id, "id must not be null");
        this.email = Objects.requireNonNull(email, "email must not be null");
        this.nickname = nickname;
        this.status = Objects.requireNonNull(status, "status must not be null");
        this.createdAt = Objects.requireNonNull(createdAt, "createdAt must not be null");
        this.updatedAt = Objects.requireNonNull(updatedAt, "updatedAt must not be null");
    }

    /**
     * Factory method: create a new User (raises UserCreatedEvent).
     */
    public static User create(String email, String nickname) {
        if (email == null || email.isBlank()) {
            throw new IllegalArgumentException("email must not be blank");
        }
        UserId id = UserId.generate();
        Instant now = Instant.now();
        User user = new User(id, email, nickname, UserStatus.ACTIVE, now, now);
        user.domainEvents.add(new UserCreatedEvent(id, email, now));
        return user;
    }

    /**
     * Reconstitute from persistence (no events raised).
     */
    public static User reconstitute(UserId id, String email, String nickname, UserStatus status, Instant createdAt, Instant updatedAt) {
        return new User(id, email, nickname, status, createdAt, updatedAt);
    }

    public void suspend() {
        if (this.status == UserStatus.DELETED) {
            throw new IllegalStateException("Cannot suspend a deleted user");
        }
        this.status = UserStatus.SUSPENDED;
        this.updatedAt = Instant.now();
    }

    public void activate() {
        if (this.status == UserStatus.DELETED) {
            throw new IllegalStateException("Cannot activate a deleted user");
        }
        this.status = UserStatus.ACTIVE;
        this.updatedAt = Instant.now();
    }

    public void markDeleted() {
        this.status = UserStatus.DELETED;
        this.updatedAt = Instant.now();
    }

    public void updateProfile(String nickname) {
        this.nickname = nickname;
        this.updatedAt = Instant.now();
    }

    // --- Getters ---

    public UserId getId() { return id; }
    public String getEmail() { return email; }
    public String getNickname() { return nickname; }
    public UserStatus getStatus() { return status; }
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
        User user = (User) other;
        return id.equals(user.id);
    }

    @Override
    public int hashCode() {
        return id.hashCode();
    }

    @Override
    public String toString() {
        return "User{id=" + id + ", email='" + email + "', status=" + status + "}";
    }
}
