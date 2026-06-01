package cc.agentcook.infrastructure.persistence.jpa;

import cc.agentcook.infrastructure.persistence.entity.ConnectorEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface JpaConnectorRepository extends JpaRepository<ConnectorEntity, UUID> {

    List<ConnectorEntity> findByPluginId(UUID pluginId);
}
