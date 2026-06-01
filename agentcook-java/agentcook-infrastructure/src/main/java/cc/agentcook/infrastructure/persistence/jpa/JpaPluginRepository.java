package cc.agentcook.infrastructure.persistence.jpa;

import cc.agentcook.domain.plugin.PluginStatus;
import cc.agentcook.infrastructure.persistence.entity.PluginEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface JpaPluginRepository extends JpaRepository<PluginEntity, UUID> {

    List<PluginEntity> findByStatus(PluginStatus status);

    Optional<PluginEntity> findByNameAndVersion(String name, String version);
}
