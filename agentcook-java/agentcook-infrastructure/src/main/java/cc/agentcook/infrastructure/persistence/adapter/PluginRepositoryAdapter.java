package cc.agentcook.infrastructure.persistence.adapter;

import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginId;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.plugin.PluginStatus;
import cc.agentcook.infrastructure.persistence.jpa.JpaPluginRepository;
import cc.agentcook.infrastructure.persistence.mapper.PluginEntityMapper;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public class PluginRepositoryAdapter implements PluginRepository {

    private final JpaPluginRepository jpa;
    private final PluginEntityMapper mapper;

    public PluginRepositoryAdapter(JpaPluginRepository jpa, PluginEntityMapper mapper) {
        this.jpa = jpa;
        this.mapper = mapper;
    }

    @Override
    public Optional<Plugin> findById(PluginId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }

    @Override
    public List<Plugin> findByStatus(PluginStatus status) {
        return jpa.findByStatus(status).stream().map(mapper::toDomain).toList();
    }

    @Override
    public Optional<Plugin> findByNameAndVersion(String name, String version) {
        return jpa.findByNameAndVersion(name, version).map(mapper::toDomain);
    }

    @Override
    public Plugin save(Plugin plugin) {
        return mapper.toDomain(jpa.save(mapper.toEntity(plugin)));
    }

    @Override
    public void delete(PluginId id) {
        jpa.deleteById(id.value());
    }
}
