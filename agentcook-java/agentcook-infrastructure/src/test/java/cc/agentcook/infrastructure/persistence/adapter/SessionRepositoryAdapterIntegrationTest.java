package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.user.User;
import cc.agentcook.infrastructure.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SessionRepositoryAdapterIntegrationTest extends IntegrationTestBase {

    @Autowired
    private SessionRepositoryAdapter adapter;

    @Autowired
    private UserRepositoryAdapter userAdapter;

    @Test
    void savesAndReadsBackSession() {
        User user = userAdapter.save(User.create("dave@example.com", "Dave"));
        Session session = Session.create(user.getId(), "Hello");

        Session saved = adapter.save(session);

        assertTrue(adapter.findById(saved.getId()).isPresent());
        assertEquals("Hello", adapter.findById(saved.getId()).get().getTitle());
    }

    @Test
    void findsAllSessionsByUserId() {
        User user = userAdapter.save(User.create("eve@example.com", "Eve"));
        adapter.save(Session.create(user.getId(), "S1"));
        adapter.save(Session.create(user.getId(), "S2"));

        List<Session> sessions = adapter.findByUserId(user.getId());

        assertEquals(2, sessions.size());
    }
}
