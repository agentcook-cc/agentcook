package cc.agentcook.domain.connector;

import cc.agentcook.domain.plugin.PluginId;

import java.util.List;
import java.util.Optional;

/**
 * Repository interface (Port) for Connector aggregate persistence.
 */
public interface ConnectorRepository {

    Optional<Connector> findById(ConnectorId id);

    List<Connector> findByPluginId(PluginId pluginId);

    Connector save(Connector connector);

    void delete(ConnectorId id);
}
