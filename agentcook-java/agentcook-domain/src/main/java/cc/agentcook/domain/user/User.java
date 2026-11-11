package cc.agentcook.domain.user;

import cc.agentcook.domain.user.event.UserCreatedEvent;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * User Aggregate Root.
 * Manages user identity, profile, credentials and lifecycle state transitions.
 *
 * <p>Credentials are held only as an opaque password <em>hash</em> produced
 * by the application layer's {@code PasswordHasher} port — the aggregate
 * never sees a raw password. Rows created before password authentication
 * existed (seed data, the old any-password dev login) carry no hash;
 * {@link #hasPassword()} lets the login flow tell them apart.</p>
 */
public class User {

    /**
     * v1 default free-tier quota per account (ADR-018 §1). Stored per-row
     * once the user is persisted so individual upgrades — e.g. a paid user
     * lift to 50 — are a single UPDATE without changing the default.
     */
    public static final int DEFAULT_FREE_QUOTA = 2;

    private final UserId id;
    private String email;
    private String nickname;
    private UserStatus status;
    private final Instant createdAt;
    private Instant updatedAt;
    private int freeQuestionsUsed;
    private int freeQuestionsQuota;
    private String passwordHash;

    private final List<Object> domainEvents = new ArrayList<>();

    private User(UserId id, String email, String nickname, UserStatus status,
                 Instant createdAt, Instant updatedAt,
                 int freeQuestionsUsed, int freeQuestionsQuota,
                 String passwordHash) {
        this.id = Objects.requireNonNull(id, "id must not be null");
        this.email = Objects.requireNonNull(email, "email must not be null");
        this.nickname = nickname;
        this.status = Objects.requireNonNull(status, "status must not be null");
        this.createdAt = Objects.requireNonNull(createdAt, "createdAt must not be null");
        this.updatedAt = Objects.requireNonNull(updatedAt, "updatedAt must not be null");
        if (freeQuestionsUsed < 0) {
            throw new IllegalArgumentException("freeQuestionsUsed must not be negative");
        }
        if (freeQuestionsQuota < 0) {
            throw new IllegalArgumentException("freeQuestionsQuota must not be negative");
        }
        this.freeQuestionsUsed = freeQuestionsUsed;
        this.freeQuestionsQuota = freeQuestionsQuota;
        this.passwordHash = (passwordHash == null || passwordHash.isBlank()) ? null : passwordHash;
    }

    /**
     * Factory method: create a new User (raises UserCreatedEvent).
     * Initialises free-tier quota to ADR-018 v1 default (2/account).
     */
    public static User create(String email, String nickname) {
        if (email == null || email.isBlank()) {
            throw new IllegalArgumentException("email must not be blank");
        }
        UserId id = UserId.generate();
        Instant now = Instant.now();
        User user = new User(id, email, nickname, UserStatus.ACTIVE, now, now,
                0, DEFAULT_FREE_QUOTA, null);
        user.domainEvents.add(new UserCreatedEvent(id, email, now));
        return user;
    }

    /**
     * Reconstitute from persistence (no events raised). Carries the
     * stored quota counters and password hash back into the aggregate
     * exactly — the DB is the source of truth once a row exists.
     *
     * @param passwordHash stored hash, or {@code null} for legacy rows
     *                     that never had a password set
     */
    public static User reconstitute(UserId id, String email, String nickname, UserStatus status,
                                    Instant createdAt, Instant updatedAt,
                                    int freeQuestionsUsed, int freeQuestionsQuota,
                                    String passwordHash) {
        return new User(id, email, nickname, status, createdAt, updatedAt,
                freeQuestionsUsed, freeQuestionsQuota, passwordHash);
    }

    /**
     * Compatibility overload (pre-V5 fixtures): reconstitutes without a
     * password hash, i.e. the state of a row created before password
     * authentication existed.
     */
    public static User reconstitute(UserId id, String email, String nickname, UserStatus status,
                                    Instant createdAt, Instant updatedAt,
                                    int freeQuestionsUsed, int freeQuestionsQuota) {
        return reconstitute(id, email, nickname, status, createdAt, updatedAt,
                freeQuestionsUsed, freeQuestionsQuota, null);
    }

    /**
     * Compatibility overload (pre-ADR-018 fixtures). Reconstitutes with
     * the v1 default quota (used=0, quota={@value #DEFAULT_FREE_QUOTA})
     * so existing tests and rows that never knew about quota land in
     * the same state V4 migration's column defaults give them.
     */
    public static User reconstitute(UserId id, String email, String nickname, UserStatus status,
                                    Instant createdAt, Instant updatedAt) {
        return reconstitute(id, email, nickname, status, createdAt, updatedAt,
                0, DEFAULT_FREE_QUOTA);
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

    /**
     * Set or replace the stored password hash. The value is opaque to the
     * domain (whatever the application layer's hasher produced); only
     * blank values are rejected so a user can never be left with an
     * "empty password" that every input would match.
     *
     * @throws IllegalArgumentException when the hash is null or blank
     * @throws IllegalStateException    when the user is deleted
     */
    public void changePasswordHash(String passwordHash) {
        if (passwordHash == null || passwordHash.isBlank()) {
            throw new IllegalArgumentException("passwordHash must not be blank");
        }
        if (this.status == UserStatus.DELETED) {
            throw new IllegalStateException("Cannot set a password on a deleted user");
        }
        this.passwordHash = passwordHash;
        this.updatedAt = Instant.now();
    }

    /**
     * Whether this user has a password hash. {@code false} for legacy /
     * seeded rows created before password authentication existed.
     */
    public boolean hasPassword() {
        return passwordHash != null;
    }

    /** Whether the account may authenticate and use the product. */
    public boolean isActive() {
        return status == UserStatus.ACTIVE;
    }

    /**
     * Consume one free-tier question, returning the new remaining count.
     * Throws if the user has already used the full quota — the caller
     * (chat router / Python middleware) is expected to interpret that as
     * "downgrade to glm-4-flash" per ADR-018 §2, not to surface a 4xx.
     *
     * @return remaining free questions after this consumption (≥ 0)
     * @throws QuotaExhaustedException when used would exceed quota
     */
    public int consumeFreeQuestion() {
        if (this.status == UserStatus.DELETED || this.status == UserStatus.SUSPENDED) {
            throw new IllegalStateException("Cannot consume quota for user in status " + this.status);
        }
        if (this.freeQuestionsUsed >= this.freeQuestionsQuota) {
            throw new QuotaExhaustedException(this.id, this.freeQuestionsQuota);
        }
        this.freeQuestionsUsed += 1;
        this.updatedAt = Instant.now();
        return this.freeQuestionsQuota - this.freeQuestionsUsed;
    }

    /**
     * Free questions still available to this user under the v1 quota.
     * Reads cleanly even when used > quota (clamped to 0) so callers
     * don't accidentally surface a negative number.
     */
    public int remainingFreeQuestions() {
        return Math.max(0, this.freeQuestionsQuota - this.freeQuestionsUsed);
    }

    // --- Getters ---

    public UserId getId() { return id; }
    public String getEmail() { return email; }
    public String getNickname() { return nickname; }
    public UserStatus getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public int getFreeQuestionsUsed() { return freeQuestionsUsed; }
    public int getFreeQuestionsQuota() { return freeQuestionsQuota; }
    /** Opaque password hash, or {@code null} when {@link #hasPassword()} is false. */
    public String getPasswordHash() { return passwordHash; }

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
