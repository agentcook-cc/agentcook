package cc.agentcook.api.auth;

import io.jsonwebtoken.Jwts;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;

/**
 * Issues HS256-signed JWTs for the dev/staging login flow. The secret
 * is the same one {@link cc.agentcook.api.config.SecurityConfig}
 * configures as the resource-server decoder key, so anything we sign
 * here verifies on the way back in.
 *
 * <p>Phase 4 replaces this with a call out to a real identity issuer
 * (Auth0 / Keycloak / cloud IAM) — at that point the resource-server
 * JWT decoder gets pointed at a JWKS URL and this class disappears.</p>
 */
@Component
public class JwtTokenIssuer {

    private final SecretKey key;
    private final Duration ttl;

    public JwtTokenIssuer(@Value("${agentcook.auth.jwt-secret}") String secret,
                          @Value("${agentcook.auth.jwt-ttl-seconds:3600}") long ttlSeconds) {
        this.key = new SecretKeySpec(secret.getBytes(), "HmacSHA256");
        this.ttl = Duration.ofSeconds(ttlSeconds);
    }

    public String issue(String subject) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(subject)
                .issuer("agentcook-java")
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }

    public long ttlSeconds() {
        return ttl.toSeconds();
    }
}
