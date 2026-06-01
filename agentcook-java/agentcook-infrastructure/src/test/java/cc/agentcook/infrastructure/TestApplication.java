package cc.agentcook.infrastructure;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration;
import org.springframework.boot.autoconfigure.data.redis.RedisRepositoriesAutoConfiguration;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

/**
 * Test-only SpringBoot fixture. Excludes Redis autoconfig — integration
 * tests use the in-memory simple cache; Redis is exercised only in dev
 * (docker-compose) and in production deployments.
 */
@SpringBootApplication(
        scanBasePackages = "cc.agentcook.infrastructure",
        exclude = {RedisAutoConfiguration.class, RedisRepositoriesAutoConfiguration.class}
)
@EntityScan(basePackages = "cc.agentcook.infrastructure")
@EnableJpaRepositories(basePackages = "cc.agentcook.infrastructure")
public class TestApplication {
}
