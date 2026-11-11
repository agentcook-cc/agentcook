package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserStatus;
import cc.agentcook.infrastructure.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class UserRepositoryAdapterIntegrationTest extends IntegrationTestBase {

    @Autowired
    private UserRepositoryAdapter adapter;

    @Autowired
    private PlatformTransactionManager transactionManager;

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

    @Test
    void passwordHashRoundTripsAndStaysNullForLegacyRows() {
        User withPassword = User.create("hash@example.com", "Hash");
        withPassword.changePasswordHash("$2a$10$abcdefghijklmnopqrstuv");
        adapter.save(withPassword);
        adapter.save(User.create("nohash@example.com", "NoHash"));

        assertEquals("$2a$10$abcdefghijklmnopqrstuv",
                adapter.findByEmail("hash@example.com").orElseThrow().getPasswordHash());
        User legacy = adapter.findByEmail("nohash@example.com").orElseThrow();
        assertFalse(legacy.hasPassword());
        assertNull(legacy.getPasswordHash());
    }

    @Test
    void findByIdForUpdateReturnsTheRowInsideATransaction() {
        User saved = adapter.save(User.create("lock@example.com", "Lock"));
        TransactionTemplate tx = new TransactionTemplate(transactionManager);

        Optional<User> locked = tx.execute(status -> adapter.findByIdForUpdate(saved.getId()));

        assertTrue(locked.isPresent());
        assertEquals("lock@example.com", locked.get().getEmail());
        assertFalse(tx.execute(status -> adapter.findByIdForUpdate(UserId.generate())).isPresent());
    }

    @Test
    void findByIdForUpdateSerialisesConcurrentReadModifyWrites() throws Exception {
        // Two transactions each read the counter, increment it and save.
        // Without the row lock both would read used=0 and the second
        // commit would overwrite the first (lost update → used=1).
        User saved = adapter.save(User.create("race@example.com", "Race"));
        UserId id = saved.getId();
        TransactionTemplate tx = new TransactionTemplate(transactionManager);
        CountDownLatch firstHoldsLock = new CountDownLatch(1);

        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<?> first = pool.submit(() -> tx.executeWithoutResult(status -> {
                User user = adapter.findByIdForUpdate(id).orElseThrow();
                firstHoldsLock.countDown();
                sleepQuietly(300);
                user.consumeFreeQuestion();
                adapter.save(user);
            }));
            assertTrue(firstHoldsLock.await(10, TimeUnit.SECONDS));
            Future<?> second = pool.submit(() -> tx.executeWithoutResult(status -> {
                User user = adapter.findByIdForUpdate(id).orElseThrow();
                user.consumeFreeQuestion();
                adapter.save(user);
            }));
            first.get(10, TimeUnit.SECONDS);
            second.get(10, TimeUnit.SECONDS);
        } finally {
            pool.shutdownNow();
        }

        assertEquals(2, adapter.findById(id).orElseThrow().getFreeQuestionsUsed());
    }

    private static void sleepQuietly(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
