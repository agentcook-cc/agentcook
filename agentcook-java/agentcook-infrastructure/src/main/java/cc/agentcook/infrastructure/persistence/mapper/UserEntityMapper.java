package cc.agentcook.infrastructure.persistence.mapper;

import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.infrastructure.persistence.entity.UserEntity;
import org.springframework.stereotype.Component;

@Component
public class UserEntityMapper {

    public UserEntity toEntity(User user) {
        return new UserEntity(
                user.getId().value(),
                user.getEmail(),
                user.getNickname(),
                user.getStatus(),
                user.getCreatedAt(),
                user.getUpdatedAt(),
                user.getFreeQuestionsUsed(),
                user.getFreeQuestionsQuota());
    }

    public User toDomain(UserEntity entity) {
        return User.reconstitute(
                UserId.from(entity.getId()),
                entity.getEmail(),
                entity.getNickname(),
                entity.getStatus(),
                entity.getCreatedAt(),
                entity.getUpdatedAt(),
                entity.getFreeQuestionsUsed(),
                entity.getFreeQuestionsQuota());
    }
}
