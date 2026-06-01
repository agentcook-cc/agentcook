package cc.agentcook.infrastructure.persistence.mapper;

import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.infrastructure.persistence.entity.ConnectorEntity;
import org.springframework.stereotype.Component;

@Component
public class ConnectorEntityMapper {

    public ConnectorEntity toEntity(Connector connector) {
        return new ConnectorEntity(
                connector.getId().value(),
                connector.getPluginId().value(),
                connector.getKind(),
                connector.getConfig(),
                connector.getStatus(),
                connector.getLastHealthCheck(),
                connector.getCreatedAt(),
                connector.getUpdatedAt());
    }

    public Connector toDomain(ConnectorEntity entity) {
        return Connector.reconstitute(
                ConnectorId.from(entity.getId()),
                PluginId.from(entity.getPluginId()),
                entity.getKind(),
                entity.getConfig(),
                entity.getStatus(),
                entity.getLastHealthCheck(),
                entity.getCreatedAt(),
                entity.getUpdatedAt());
    }
}
