package cc.agentcook.infrastructure.config;

import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Configuration;

/**
 * Activates Spring Cache abstraction. Backend (simple in-memory or
 * Redis) is selected via {@code spring.cache.type} per profile —
 * default {@code simple}, docker profile overrides to {@code redis}.
 */
@Configuration
@EnableCaching
public class CacheConfig {
}
