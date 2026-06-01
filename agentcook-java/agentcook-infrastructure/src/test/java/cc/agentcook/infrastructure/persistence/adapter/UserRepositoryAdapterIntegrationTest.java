package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserStatus;
import cc.agentcook.infrastructure.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class UserRepositoryAdapterIntegrationTest extends IntegrationTestBase {

    @Autowired
    private UserRepositoryAdapter adapter;

    @Test
    void savesAndReadsBackUser() {
        User user = User.create("alice@example.com", "Alice");
        User saved = adapter.save(user);

        Optional<User> loaded = adapter.findById(saved.getId());

        assertTrue(loaded.isPresent());
        assertEquals("alice@example.com", loaded.get().getEmail());
        assertEquals(UserStatus.ACTIVE, loaded.get().getStatus());
    }

    @Test
    void findsByEmailAndChecksExists() {
        adapter.save(User.create("bob@example.com", "Bob"));

        assertTrue(adapter.existsByEmail("bob@example.com"));
        assertFalse(adapter.existsByEmail("missing@example.com"));

        Optional<User> bob = adapter.findByEmail("bob@example.com");
        assertTrue(bob.isPresent());
        assertNotNull(bob.get().getId());
    }

    @Test
    void deletesUser() {
        User saved = adapter.save(User.create("carol@example.com", "Carol"));

        adapter.delete(saved.getId());

        assertFalse(adapter.findById(saved.getId()).isPresent());
    }
}
