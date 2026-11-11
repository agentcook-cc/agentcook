package cc.agentcook.domain.user;

import java.util.List;
import java.util.Optional;

/**
 * Repository interface (Port) for User aggregate persistence.
 * Implementation lives in the infrastructure layer.
 */
public interface UserRepository {

    Optional<User> findById(UserId id);

    /**
     * Load a user for a read-modify-write and hold a row-level write lock
     * on it until the surrounding transaction ends. Concurrent callers
     * block until the lock holder commits and then see its changes, so
     * two writers can never both start from the same stale snapshot
     * (e.g. two parallel quota consumptions both reading {@code used=1}).
     *
     * <p>Must be called inside a transaction. Never served from a cache.</p>
     */
    Optional<User> findByIdForUpdate(UserId id);

    Optional<User> findByEmail(String email);

    List<User> findAll();

    List<User> findByStatus(UserStatus status);

    User save(User user);

    void delete(UserId id);

    boolean existsByEmail(String email);
}
