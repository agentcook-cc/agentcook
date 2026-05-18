package cc.agentcook.domain.plugin;

import java.util.List;
import java.util.Optional;

/**
 * Repository interface (Port) for Plugin aggregate persistence.
 */
public interface PluginRepository {

    Optional<Plugin> findById(PluginId id);

    List<Plugin> findByStatus(PluginStatus status);

    Optional<Plugin> findByNameAndVersion(String name, String version);

    Plugin save(Plugin plugin);

    void delete(PluginId id);
}
