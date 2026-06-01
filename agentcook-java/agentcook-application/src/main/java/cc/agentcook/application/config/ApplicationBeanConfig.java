package cc.agentcook.application.config;

import cc.agentcook.domain.connector.ConnectorRepository;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.plugin.PluginRepository;
import cc.agentcook.domain.service.PluginActivationService;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Promotes plain-Java domain services into Spring beans without
 * polluting the domain layer with Spring annotations.
 */
@Configuration
public class ApplicationBeanConfig {

    @Bean
    public PluginActivationService pluginActivationService(PermissionRepository permissionRepository,
                                                           ConnectorRepository connectorRepository,
                                                           PluginRepository pluginRepository) {
        return new PluginActivationService(permissionRepository, connectorRepository, pluginRepository);
    }
}
