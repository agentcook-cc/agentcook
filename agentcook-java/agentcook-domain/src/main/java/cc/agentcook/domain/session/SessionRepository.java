package cc.agentcook.domain.session;

import cc.agentcook.domain.user.UserId;

import java.util.List;
import java.util.Optional;

/**
 * Repository interface (Port) for Session aggregate persistence.
 */
public interface SessionRepository {

    Optional<Session> findById(SessionId id);

    List<Session> findByUserId(UserId userId);

    Session save(Session session);

    void delete(SessionId id);
}
