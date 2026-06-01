package cc.agentcook.infrastructure.persistence.mapper;

import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionId;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.infrastructure.persistence.entity.PermissionEntity;
import org.springframework.stereotype.Component;

@Component
public class PermissionEntityMapper {

    public PermissionEntity toEntity(Permission permission) {
        return new PermissionEntity(
                permission.getId().value(),
                permission.getUserId().value(),
                permission.getResource(),
                permission.getAction(),
                permission.getEffect(),
                permission.getCreatedAt());
    }

    public Permission toDomain(PermissionEntity entity) {
        return Permission.reconstitute(
                PermissionId.from(entity.getId()),
                UserId.from(entity.getUserId()),
                entity.getResource(),
                entity.getAction(),
                entity.getEffect(),
                entity.getCreatedAt());
    }
}
