package cc.agentcook.domain.user;

import cc.agentcook.domain.user.event.UserCreatedEvent;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class UserTest {

    @Test
    void createUser_shouldSetActiveStatusAndRaiseEvent() {
        User user = User.create("alice@example.com", "Alice");

        assertNotNull(user.getId());
        assertEquals("alice@example.com", user.getEmail());
        assertEquals("Alice", user.getNickname());
        assertEquals(UserStatus.ACTIVE, user.getStatus());
        assertNotNull(user.getCreatedAt());
        assertEquals(1, user.getDomainEvents().size());
        assertInstanceOf(UserCreatedEvent.class, user.getDomainEvents().get(0));
    }

    @Test
    void createUser_withBlankEmail_shouldThrow() {
        assertThrows(IllegalArgumentException.class, () -> User.create("", "Alice"));
        assertThrows(IllegalArgumentException.class, () -> User.create(null, "Alice"));
    }

    @Test
    void suspend_activeUser_shouldTransitionToSuspended() {
        User user = User.create("bob@example.com", "Bob");
        user.suspend();
        assertEquals(UserStatus.SUSPENDED, user.getStatus());
    }

    @Test
    void activate_suspendedUser_shouldTransitionToActive() {
        User user = User.create("bob@example.com", "Bob");
        user.suspend();
        user.activate();
        assertEquals(UserStatus.ACTIVE, user.getStatus());
    }

    @Test
    void suspend_deletedUser_shouldThrow() {
        User user = User.create("bob@example.com", "Bob");
        user.markDeleted();
        assertThrows(IllegalStateException.class, user::suspend);
    }

    @Test
    void activate_deletedUser_shouldThrow() {
        User user = User.create("bob@example.com", "Bob");
        user.markDeleted();
        assertThrows(IllegalStateException.class, user::activate);
    }

    @Test
    void markDeleted_shouldTransitionToDeleted() {
        User user = User.create("carol@example.com", "Carol");
        user.markDeleted();
        assertEquals(UserStatus.DELETED, user.getStatus());
    }

    @Test
    void equals_sameId_shouldBeEqual() {
        UUID rawId = UUID.randomUUID();
        UserId id = UserId.from(rawId);
        User user1 = User.reconstitute(id, "a@b.com", "A", UserStatus.ACTIVE,
                java.time.Instant.now(), java.time.Instant.now());
        User user2 = User.reconstitute(id, "different@b.com", "B", UserStatus.SUSPENDED,
                java.time.Instant.now(), java.time.Instant.now());
        assertEquals(user1, user2);
        assertEquals(user1.hashCode(), user2.hashCode());
    }

    @Test
    void equals_differentId_shouldNotBeEqual() {
        User user1 = User.create("a@b.com", "A");
        User user2 = User.create("a@b.com", "A");
        assertNotEquals(user1, user2);
    }

    @Test
    void clearDomainEvents_shouldEmptyList() {
        User user = User.create("x@y.com", "X");
        assertEquals(1, user.getDomainEvents().size());
        user.clearDomainEvents();
        assertTrue(user.getDomainEvents().isEmpty());
    }

    // --- ADR-018 quota tests ---

    @Test
    void createUser_shouldInitialiseQuotaToV1Default() {
        User user = User.create("quota@example.com", "Q");
        assertEquals(0, user.getFreeQuestionsUsed());
        assertEquals(User.DEFAULT_FREE_QUOTA, user.getFreeQuestionsQuota());
        assertEquals(User.DEFAULT_FREE_QUOTA, user.remainingFreeQuestions());
    }

    @Test
    void consumeFreeQuestion_underQuota_shouldIncrementAndReturnRemaining() {
        User user = User.create("q1@example.com", "Q1");
        int remaining = user.consumeFreeQuestion();
        assertEquals(1, user.getFreeQuestionsUsed());
        assertEquals(User.DEFAULT_FREE_QUOTA - 1, remaining);
    }

    @Test
    void consumeFreeQuestion_atQuotaCeiling_shouldThrow() {
        User user = User.create("q2@example.com", "Q2");
        // Consume DEFAULT_FREE_QUOTA (= 2 in v1) — the last successful
        // call returns 0 remaining; the next must throw, NOT silently
        // succeed at -1.
        for (int i = 0; i < User.DEFAULT_FREE_QUOTA; i++) {
            user.consumeFreeQuestion();
        }
        assertEquals(0, user.remainingFreeQuestions());
        QuotaExhaustedException ex = assertThrows(
                QuotaExhaustedException.class, user::consumeFreeQuestion);
        assertEquals(user.getId(), ex.getUserId());
        assertEquals(User.DEFAULT_FREE_QUOTA, ex.getQuota());
        // Verify no silent increment past the ceiling.
        assertEquals(User.DEFAULT_FREE_QUOTA, user.getFreeQuestionsUsed());
    }

    @Test
    void consumeFreeQuestion_suspendedUser_shouldThrowIllegalState() {
        User user = User.create("q3@example.com", "Q3");
        user.suspend();
        assertThrows(IllegalStateException.class, user::consumeFreeQuestion);
        // Counter unchanged on rejected attempt.
        assertEquals(0, user.getFreeQuestionsUsed());
    }

    @Test
    void consumeFreeQuestion_deletedUser_shouldThrowIllegalState() {
        User user = User.create("q4@example.com", "Q4");
        user.markDeleted();
        assertThrows(IllegalStateException.class, user::consumeFreeQuestion);
    }

    @Test
    void reconstituteWithQuota_shouldCarryStoredCounters() {
        UserId id = UserId.generate();
        java.time.Instant now = java.time.Instant.now();
        User user = User.reconstitute(id, "stored@example.com", "S", UserStatus.ACTIVE,
                now, now, /*used=*/ 1, /*quota=*/ 5);
        assertEquals(1, user.getFreeQuestionsUsed());
        assertEquals(5, user.getFreeQuestionsQuota());
        assertEquals(4, user.remainingFreeQuestions());
        // Reconstitute must NOT raise events (DB load isn't a creation).
        assertTrue(user.getDomainEvents().isEmpty());
    }

    @Test
    void reconstitute_legacy6ArgOverload_appliesDefaultQuota() {
        // Pre-ADR-018 fixtures use the 6-arg overload — they must land
        // in the same state V4's column defaults give a fresh row.
        UserId id = UserId.generate();
        java.time.Instant now = java.time.Instant.now();
        User user = User.reconstitute(id, "legacy@example.com", "L", UserStatus.ACTIVE, now, now);
        assertEquals(0, user.getFreeQuestionsUsed());
        assertEquals(User.DEFAULT_FREE_QUOTA, user.getFreeQuestionsQuota());
    }
}
