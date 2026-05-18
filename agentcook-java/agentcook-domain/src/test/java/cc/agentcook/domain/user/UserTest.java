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
}
