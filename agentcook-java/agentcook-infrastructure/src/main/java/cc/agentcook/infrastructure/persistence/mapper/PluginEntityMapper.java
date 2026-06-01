package cc.agentcook.infrastructure.persistence.mapper;

import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.infrastructure.persistence.entity.PluginEntity;
import org.springframework.stereotype.Component;

@Component
public class PluginEntityMapper {

    public PluginEntity toEntity(Plugin plugin) {
        return new PluginEntity(
                plugin.getId().value(),
                plugin.getName(),
                plugin.getVersion(),
                plugin.getKind(),
                plugin.getDescription(),
                plugin.getStatus(),
                plugin.getCreatedAt(),
                plugin.getUpdatedAt());
    }

    public Plugin toDomain(PluginEntity entity) {
        return Plugin.reconstitute(
                PluginId.from(entity.getId()),
                entity.getName(),
                entity.getVersion(),
                entity.getKind(),
                entity.getDescription(),
                entity.getStatus(),
                entity.getCreatedAt(),
                entity.getUpdatedAt());
    }
}
