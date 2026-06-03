package cc.agentcook.api.auth;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Five boundary cases for {@link TurnstileVerifier} — same JDK
 * {@code HttpServer} mocking pattern Day 45 used for
 * {@code PythonUpstreamHealthIndicator}.
 *
 * <p>Test #1 covers dev-mode short-circuit; #2-#3 cover the two
 * happy-path Cloudflare responses; #4-#5 cover the two failure paths
 * (5xx, unreachable). Together they pin every conditional in the
 * verifier method body.</p>
 */
class TurnstileVerifierTest {

    private HttpServer siteverifyStub;

    @AfterEach
    void stopStub() {
        if (siteverifyStub != null) siteverifyStub.stop(0);
    }

    @Test
    @DisplayName("dev/test profile: empty secret short-circuits to true (no Cloudflare call)")
    void verify_emptySecret_returnsTrue() {
        // Use a real (but unused) URL — if the verifier ever calls it
        // the test will hang on connect, surfacing the bug clearly.
        TurnstileVerifier verifier = new TurnstileVerifier("", "http://127.0.0.1:1/siteverify");

        assertThat(verifier.verify("any-token", "1.2.3.4")).isTrue();
        assertThat(verifier.verify(null, null)).isTrue();
    }

    @Test
    @DisplayName("success: Cloudflare 200 + body declares success=true → returns true")
    void verify_siteverifyReturnsSuccessTrue_returnsTrue() throws Exception {
        AtomicReference<String> capturedBody = new AtomicReference<>();
        siteverifyStub = startStub(exchange -> {
            capturedBody.set(new String(
                    exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] body = "{\"success\":true,\"hostname\":\"example.com\"}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(body);
            }
        });

        TurnstileVerifier verifier = new TurnstileVerifier("real-secret", url());

        assertThat(verifier.verify("valid-token", "203.0.113.5")).isTrue();
        assertThat(capturedBody.get())
                .as("siteverify form body must carry secret + response + remoteip")
                .contains("secret=real-secret")
                .contains("response=valid-token")
                .contains("remoteip=203.0.113.5");
    }

    @Test
    @DisplayName("failure: Cloudflare 200 + body declares success=false → returns false")
    void verify_siteverifyReturnsSuccessFalse_returnsFalse() throws Exception {
        siteverifyStub = startStub(exchange -> {
            byte[] body = ("{\"success\":false,"
                    + "\"error-codes\":[\"invalid-input-response\"]}").getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(body);
            }
        });

        TurnstileVerifier verifier = new TurnstileVerifier("real-secret", url());

        assertThat(verifier.verify("bad-token", null)).isFalse();
    }

    @Test
    @DisplayName("fail closed: Cloudflare 5xx → returns false (don't let unverified traffic through)")
    void verify_siteverifyReturnsHttp503_returnsFalse() throws Exception {
        siteverifyStub = startStub(exchange -> {
            exchange.sendResponseHeaders(503, -1);
            exchange.close();
        });

        TurnstileVerifier verifier = new TurnstileVerifier("real-secret", url());

        assertThat(verifier.verify("some-token", "10.0.0.1")).isFalse();
    }

    @Test
    @DisplayName("fail closed: siteverify endpoint unreachable → returns false")
    void verify_siteverifyUnreachable_returnsFalse() {
        // Port 1 is reserved + never listening — deterministic
        // connection-refused without relying on a transient port.
        TurnstileVerifier verifier = new TurnstileVerifier(
                "real-secret", "http://127.0.0.1:1/siteverify");

        assertThat(verifier.verify("any-token", "192.0.2.1")).isFalse();
    }

    // --- helpers ---

    private HttpServer startStub(com.sun.net.httpserver.HttpHandler handler) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/siteverify", handler);
        server.start();
        return server;
    }

    private String url() {
        return "http://127.0.0.1:" + siteverifyStub.getAddress().getPort() + "/siteverify";
    }
}
