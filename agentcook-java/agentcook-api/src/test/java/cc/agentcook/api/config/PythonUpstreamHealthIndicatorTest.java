package cc.agentcook.api.config;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.Status;

import java.net.InetSocketAddress;

import static org.assertj.core.api.Assertions.assertThat;

class PythonUpstreamHealthIndicatorTest {

    @Test
    void unreachableUpstreamReportsUnknownNotDown() {
        // Port 1 is reserved and never listening — deterministic connection refused
        // without relying on flaky transient ports.
        PythonUpstreamHealthIndicator indicator =
                new PythonUpstreamHealthIndicator("http://127.0.0.1:1");

        Health health = indicator.health();

        assertThat(health.getStatus()).isEqualTo(Status.UNKNOWN);
        assertThat(health.getDetails())
                .containsEntry("python_upstream", "http://127.0.0.1:1/health")
                .containsKey("error");
    }

    @Test
    void reachableUpstreamReportsUp() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/health", exchange -> {
            byte[] body = "ok".getBytes();
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        try {
            String baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
            PythonUpstreamHealthIndicator indicator = new PythonUpstreamHealthIndicator(baseUrl);

            Health health = indicator.health();

            assertThat(health.getStatus()).isEqualTo(Status.UP);
            assertThat(health.getDetails())
                    .containsEntry("python_upstream", baseUrl + "/health");
        } finally {
            server.stop(0);
        }
    }

    @Test
    void non200UpstreamReportsUnknown() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/health", exchange -> {
            exchange.sendResponseHeaders(503, -1);
            exchange.close();
        });
        server.start();
        try {
            String baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
            PythonUpstreamHealthIndicator indicator = new PythonUpstreamHealthIndicator(baseUrl);

            Health health = indicator.health();

            assertThat(health.getStatus()).isEqualTo(Status.UNKNOWN);
            assertThat(health.getDetails()).containsEntry("status", 503);
        } finally {
            server.stop(0);
        }
    }

    @Test
    void baseUrlTrailingSlashIsNormalized() {
        PythonUpstreamHealthIndicator indicator =
                new PythonUpstreamHealthIndicator("http://127.0.0.1:1///");

        Health health = indicator.health();

        assertThat(health.getDetails())
                .containsEntry("python_upstream", "http://127.0.0.1:1/health");
    }
}
