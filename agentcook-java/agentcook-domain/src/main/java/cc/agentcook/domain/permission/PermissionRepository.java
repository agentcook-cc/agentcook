package cc.agentcook.domain.permission;

import cc.agentcook.domain.user.UserId;

import java.util.List;
import java.util.Optional;

/**
 * Repository interface (Port) for Permission aggregate persistence.
 */
public interface PermissionRepository {

    Optional<Permission> findById(PermissionId id);

    List<Permission> findByUserId(UserId userId);

    List<Permission> findByUserIdAndResource(UserId userId, String resource);

    Permission save(Permission permission);

    void delete(PermissionId id);
}
