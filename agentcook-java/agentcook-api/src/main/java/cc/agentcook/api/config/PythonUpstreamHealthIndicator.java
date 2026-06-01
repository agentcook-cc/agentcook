package cc.agentcook.api.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import java.net.HttpURLConnection;
import java.net.URI;

/**
 * Reports the reachability of the Python upstream as a soft dependency.
 * Java admin-bff manages user/session/plugin/connector/permission/auth
 * autonomously; only chat (gRPC bridge) needs Python. So an unreachable
 * Python upstream must not make Java's aggregated /actuator/health DOWN —
 * it returns UNKNOWN, which Spring Boot's default status order treats as
 * UP at the group level while still surfacing the detail to operators.
 */
@Component
public class PythonUpstreamHealthIndicator implements HealthIndicator {

    private final String healthUrl;

    public PythonUpstreamHealthIndicator(
            @Value("${agentcook.python-upstream-url:http://localhost:8000}") String baseUrl) {
        this.healthUrl = baseUrl.replaceAll("/+$", "") + "/health";
    }

    @Override
    public Health health() {
        try {
            HttpURLConnection connection = (HttpURLConnection)
                    URI.create(healthUrl).toURL().openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(2000);
            int status = connection.getResponseCode();
            connection.disconnect();

            if (status == 200) {
                return Health.up()
                        .withDetail("python_upstream", healthUrl)
                        .build();
            }
            return Health.unknown()
                    .withDetail("python_upstream", healthUrl)
                    .withDetail("status", status)
                    .build();
        } catch (Exception e) {
            return Health.unknown()
                    .withDetail("python_upstream", healthUrl)
                    .withDetail("error", e.getMessage())
                    .build();
        }
    }
}
