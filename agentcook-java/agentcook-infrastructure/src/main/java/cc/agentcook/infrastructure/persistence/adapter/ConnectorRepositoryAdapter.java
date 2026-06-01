package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.connector.Connector;
import cc.agentcook.domain.connector.ConnectorId;
import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.infrastructure.persistence.jpa.JpaConnectorRepository;
import cc.agentcook.infrastructure.persistence.mapper.ConnectorEntityMapper;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class ConnectorRepositoryAdapter implements ConnectorRepository {

    private final JpaConnectorRepository jpa;
    private final ConnectorEntityMapper mapper;

    public ConnectorRepositoryAdapter(JpaConnectorRepository jpa, ConnectorEntityMapper mapper) {
        this.jpa = jpa;
        this.mapper = mapper;
    }

    @Override
    public Optional<Connector> findById(ConnectorId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }

    @Override
    public List<Connector> findByPluginId(PluginId pluginId) {
        return jpa.findByPluginId(pluginId.value()).stream().map(mapper::toDomain).toList();
    }

    @Override
    public Connector save(Connector connector) {
        return mapper.toDomain(jpa.save(mapper.toEntity(connector)));
    }

    @Override
    public void delete(ConnectorId id) {
        jpa.deleteById(id.value());
    }
}
