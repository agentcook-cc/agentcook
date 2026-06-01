package cc.agentcook.infrastructure.persistence.jpa;

import cc.agentcook.infrastructure.persistence.entity.PermissionEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface JpaPermissionRepository extends JpaRepository<PermissionEntity, UUID> {

    List<PermissionEntity> findByUserIdAndResource(UUID userId, String resource);
}
