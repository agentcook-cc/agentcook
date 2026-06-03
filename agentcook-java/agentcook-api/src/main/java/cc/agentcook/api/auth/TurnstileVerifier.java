package cc.agentcook.api.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

/**
 * Cloudflare Turnstile token verifier (ADR draft
 * <code>draft-cloudflare-turnstile-rate-limit-design.md</code> §2.2.2).
 *
 * <p>POSTs {@code secret + response + remoteip} to Cloudflare's
 * {@code /turnstile/v0/siteverify} endpoint and returns whether the
 * response body declares {@code "success": true}.</p>
 *
 * <p><b>Dev / test mode:</b> if {@code agentcook.turnstile.secret} is
 * empty (default), verification is short-circuited to <em>true</em>.
 * Phase 3 dev login / Phase 5 tests run without a Cloudflare account
 * provisioned, and forcing every PR contributor to obtain one would
 * grind the inner loop to a halt. Prod must set the secret via env
 * (`AGENTCOOK_TURNSTILE_SECRET`) for verification to actually run.</p>
 *
 * <p><b>Fail closed:</b> when the upstream returns a non-200, a
 * connect/read timeout fires, or the body cannot be parsed, this
 * returns <em>false</em>. Letting unverified traffic through on a
 * Cloudflare outage would defeat the purpose of the gate.</p>
 */
@Component
public class TurnstileVerifier {

    private static final Logger log = LoggerFactory.getLogger(TurnstileVerifier.class);

    /** Cloudflare's published siteverify endpoint. */
    static final String DEFAULT_SITEVERIFY_URL =
            "https://challenges.cloudflare.com/turnstile/v0/siteverify";

    /** Connect / read timeouts in milliseconds. */
    private static final int CONNECT_TIMEOUT_MS = 3000;
    private static final int READ_TIMEOUT_MS = 5000;

    private final String secret;
    private final String siteverifyUrl;

    public TurnstileVerifier(
            @Value("${agentcook.turnstile.secret:}") String secret,
            @Value("${agentcook.turnstile.siteverify-url:" + DEFAULT_SITEVERIFY_URL + "}")
            String siteverifyUrl) {
        this.secret = secret == null ? "" : secret;
        this.siteverifyUrl = siteverifyUrl;
    }

    /**
     * Verify a Turnstile token issued by the frontend widget.
     *
     * @param token    response token from {@code <Turnstile>} widget
     * @param remoteIp client IP (optional; pass null/blank if unknown)
     * @return {@code true} if Cloudflare confirms the token OR if the
     *         secret is unset (dev/test mode). {@code false} on any
     *         failure path.
     */
    public boolean verify(String token, String remoteIp) {
        if (secret.isEmpty()) {
            return true;
        }
        if (token == null || token.isBlank()) {
            return false;
        }
        HttpURLConnection conn = null;
        try {
            URI uri = URI.create(siteverifyUrl);
            conn = (HttpURLConnection) uri.toURL().openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
            conn.setConnectTimeout(CONNECT_TIMEOUT_MS);
            conn.setReadTimeout(READ_TIMEOUT_MS);
            conn.setDoOutput(true);

            String body = buildFormBody(token, remoteIp);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(body.getBytes(StandardCharsets.UTF_8));
            }

            int status = conn.getResponseCode();
            if (status != 200) {
                log.warn("Turnstile siteverify returned HTTP {} — failing closed", status);
                return false;
            }
            String responseBody = new String(
                    conn.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            return responseBody.contains("\"success\":true")
                    || responseBody.contains("\"success\": true");
        } catch (IOException e) {
            log.warn("Turnstile siteverify unreachable — failing closed: {}", e.getMessage());
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private String buildFormBody(String token, String remoteIp) {
        StringBuilder body = new StringBuilder();
        body.append("secret=").append(enc(secret));
        body.append("&response=").append(enc(token));
        if (remoteIp != null && !remoteIp.isBlank()) {
            body.append("&remoteip=").append(enc(remoteIp));
        }
        return body.toString();
    }

    private static String enc(String s) {
        return URLEncoder.encode(s, StandardCharsets.UTF_8);
    }
}
