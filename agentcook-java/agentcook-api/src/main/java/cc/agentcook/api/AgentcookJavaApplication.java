package cc.agentcook.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

@SpringBootApplication(scanBasePackages = "cc.agentcook")
@EntityScan(basePackages = "cc.agentcook.infrastructure")
@EnableJpaRepositories(basePackages = "cc.agentcook.infrastructure")
public class AgentcookJavaApplication {

    public static void main(String[] args) {
        SpringApplication.run(AgentcookJavaApplication.class, args);
    }
}
