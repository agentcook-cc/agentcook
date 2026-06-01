package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.infrastructure.persistence.jpa.JpaSessionRepository;
import cc.agentcook.infrastructure.persistence.mapper.SessionEntityMapper;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class SessionRepositoryAdapter implements SessionRepository {

    private final JpaSessionRepository jpa;
    private final SessionEntityMapper mapper;

    public SessionRepositoryAdapter(JpaSessionRepository jpa, SessionEntityMapper mapper) {
        this.jpa = jpa;
        this.mapper = mapper;
    }

    @Override
    @Cacheable(value = "sessions", key = "#id.value()")
    public Optional<Session> findById(SessionId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }

    @Override
    public List<Session> findByUserId(UserId userId) {
        return jpa.findByUserId(userId.value()).stream().map(mapper::toDomain).toList();
    }

    @Override
    @CacheEvict(value = "sessions", key = "#session.id.value()")
    public Session save(Session session) {
        return mapper.toDomain(jpa.save(mapper.toEntity(session)));
    }

    @Override
    @CacheEvict(value = "sessions", key = "#id.value()")
    public void delete(SessionId id) {
        jpa.deleteById(id.value());
    }
}
