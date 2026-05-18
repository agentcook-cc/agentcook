package cc.agentcook.domain.user;

import java.util.Optional;

/**
 * Repository interface (Port) for User aggregate persistence.
 * Implementation lives in the infrastructure layer.
 */
public interface UserRepository {

    Optional<User> findById(UserId id);

    Optional<User> findByEmail(String email);

    User save(User user);

    void delete(UserId id);

    boolean existsByEmail(String email);
}
