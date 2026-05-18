package cc.agentcook.domain.session;

import cc.agentcook.domain.session.event.SessionCreatedEvent;
import cc.agentcook.domain.user.UserId;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class SessionTest {

    @Test
    void create_shouldSetActiveStatusAndRaiseEvent() {
        UserId userId = UserId.generate();
        Session session = Session.create(userId, "Test Chat");

        assertNotNull(session.getId());
        assertEquals(userId, session.getUserId());
        assertEquals("Test Chat", session.getTitle());
        assertEquals(SessionStatus.ACTIVE, session.getStatus());
        assertEquals(1, session.getDomainEvents().size());
        assertInstanceOf(SessionCreatedEvent.class, session.getDomainEvents().get(0));
    }

    @Test
    void create_withNullUserId_shouldThrow() {
        assertThrows(IllegalArgumentException.class, () -> Session.create(null, "title"));
    }

    @Test
    void archive_activeSession_shouldTransition() {
        Session session = Session.create(UserId.generate(), "Chat");
        session.archive();
        assertEquals(SessionStatus.ARCHIVED, session.getStatus());
    }

    @Test
    void activate_archivedSession_shouldTransition() {
        Session session = Session.create(UserId.generate(), "Chat");
        session.archive();
        session.activate();
        assertEquals(SessionStatus.ACTIVE, session.getStatus());
    }

    @Test
    void archive_deletedSession_shouldThrow() {
        Session session = Session.create(UserId.generate(), "Chat");
        session.markDeleted();
        assertThrows(IllegalStateException.class, session::archive);
    }

    @Test
    void activate_deletedSession_shouldThrow() {
        Session session = Session.create(UserId.generate(), "Chat");
        session.markDeleted();
        assertThrows(IllegalStateException.class, session::activate);
    }

    @Test
    void updateTitle_shouldChangeTitle() {
        Session session = Session.create(UserId.generate(), "Old Title");
        session.updateTitle("New Title");
        assertEquals("New Title", session.getTitle());
    }

    @Test
    void equals_sameId_shouldBeEqual() {
        SessionId id = SessionId.generate();
        Session s1 = Session.reconstitute(id, UserId.generate(), "A", SessionStatus.ACTIVE,
                java.time.Instant.now(), java.time.Instant.now());
        Session s2 = Session.reconstitute(id, UserId.generate(), "B", SessionStatus.ARCHIVED,
                java.time.Instant.now(), java.time.Instant.now());
        assertEquals(s1, s2);
    }
}
