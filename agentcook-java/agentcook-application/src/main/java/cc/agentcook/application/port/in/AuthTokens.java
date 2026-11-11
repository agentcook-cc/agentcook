package cc.agentcook.application.port.in;

import java.util.Objects;

/**
 * Result of a successful register / login / refresh: a short-lived access
 * token for API calls and a long-lived refresh token to obtain the next
 * pair. Lifetimes are in seconds.
 */
public record AuthTokens(String accessToken, long accessExpiresInSeconds,
                         String refreshToken, long refreshExpiresInSeconds) {

    public AuthTokens {
        Objects.requireNonNull(accessToken, "accessToken must not be null");
        Objects.requireNonNull(refreshToken, "refreshToken must not be null");
    }

    @Override
    public String toString() {
        return "AuthTokens[accessExpiresInSeconds=" + accessExpiresInSeconds
                + ", refreshExpiresInSeconds=" + refreshExpiresInSeconds + "]";
    }
}
