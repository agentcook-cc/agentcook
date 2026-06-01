package cc.agentcook.infrastructure.persistence.mapper;

import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.infrastructure.persistence.entity.SessionEntity;
import org.springframework.stereotype.Component;

@Component
public class SessionEntityMapper {

    public SessionEntity toEntity(Session session) {
        return new SessionEntity(
                session.getId().value(),
                session.getUserId().value(),
                session.getTitle(),
                session.getStatus(),
                session.getCreatedAt(),
                session.getUpdatedAt());
    }

    public Session toDomain(SessionEntity entity) {
        return Session.reconstitute(
                SessionId.from(entity.getId()),
                UserId.from(entity.getUserId()),
                entity.getTitle(),
                entity.getStatus(),
                entity.getCreatedAt(),
                entity.getUpdatedAt());
    }
}
