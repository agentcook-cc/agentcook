package cc.agentcook.api.auth;

import cc.agentcook.application.exception.InvalidRefreshTokenException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.out.AuthTokenIssuer;
import cc.agentcook.domain.user.LoginIdentity;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Collections;
import java.util.Date;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Issues and verifies the HS256-signed JWTs handed out by
 * {@code /api/v1/auth/*}. The secret is the same one
 * {@link cc.agentcook.api.config.SecurityConfig} configures as the
 * resource-server decoder key and the Python runtime verifies with
 * ({@code AGENTCOOK_JWT_SECRET}), so a token signed here is accepted by
 * both services.
 *
 * <p><b>Access token</b> claims: {@code sub} (user UUID), {@code iss},
 * {@code iat}, {@code exp}, {@code typ: "access"}, {@code roles}
 * ({@code ["user"]} plus {@code "admin"}), {@code scope} ({@code "chat"}
 * plus {@code " admin"}) and {@code preferred_username} (the handle the
 * user signs in with).</p>
 *
 * <p><b>Refresh token</b> claims: {@code sub}, {@code iss}, {@code iat},
 * {@code exp}, {@code typ: "refresh"} and a random {@code jti}. Both
 * services refuse a refresh token where an access token is expected.</p>
 *
 * <p>Admins are configured by identity in {@code agentcook.auth.admins}
 * (comma-separated usernames or e-mails, normalised exactly like a login
 * handle) and get the admin role when a token is issued — demoting
 * someone takes effect on their next refresh.</p>
 */
@Component
public class JwtTokenIssuer implements AuthTokenIssuer {

    private static final Logger log = LoggerFactory.getLogger(JwtTokenIssuer.class);

    /** {@code iss} claim of every token we sign (and the only one we accept). */
    public static final String ISSUER = "agentcook-java";

    /** HS256 needs a key of at least 256 bits; both services enforce it. */
    public static final int MIN_SECRET_BYTES = 32;

    public static final String CLAIM_TYPE = "typ";
    public static final String CLAIM_ROLES = "roles";
    public static final String CLAIM_SCOPE = "scope";
    public static final String CLAIM_PREFERRED_USERNAME = "preferred_username";
    public static final String TYPE_ACCESS = "access";
    public static final String TYPE_REFRESH = "refresh";
    public static final String ROLE_USER = "user";
    public static final String ROLE_ADMIN = "admin";
    public static final String SCOPE_CHAT = "chat";
    public static final String SCOPE_ADMIN = "admin";

    private final SecretKey key;
    private final Duration ttl;
    private final Duration refreshTtl;
    private final Set<String> adminEmails;

    public JwtTokenIssuer(@Value("${agentcook.auth.jwt-secret}") String secret,
                          @Value("${agentcook.auth.jwt-ttl-seconds:3600}") long ttlSeconds,
                          @Value("${agentcook.auth.refresh-ttl-seconds:2592000}") long refreshTtlSeconds,
                          @Value("${agentcook.auth.admins:}") String admins) {
        this.key = signingKey(secret);
        this.ttl = Duration.ofSeconds(ttlSeconds);
        this.refreshTtl = Duration.ofSeconds(refreshTtlSeconds);
        this.adminEmails = parseAdmins(admins);
    }

    /**
     * The HMAC key for a configured secret (UTF-8 bytes, as the Python
     * runtime encodes it). Fails at startup rather than on the first
     * login when the secret is too short for HS256.
     */
    public static SecretKeySpec signingKey(String secret) {
        byte[] bytes = secret == null ? new byte[0] : secret.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < MIN_SECRET_BYTES) {
            throw new IllegalStateException("agentcook.auth.jwt-secret (AGENTCOOK_AUTH_JWT_SECRET) must be at least "
                    + MIN_SECRET_BYTES + " bytes for HS256, got " + bytes.length);
        }
        return new SecretKeySpec(bytes, "HmacSHA256");
    }

    @Override
    public AuthTokens issue(User user) {
        String subject = user.getId().value().toString();
        String accessToken = issueAccessToken(subject, LoginIdentity.handleOf(user.getEmail()), isAdmin(user));
        return new AuthTokens(accessToken, ttlSeconds(), issueRefreshToken(subject), refreshTtlSeconds());
    }

    /** Sign an access token. Public for tests that need a token for an arbitrary subject. */
    public String issueAccessToken(String subject, String preferredUsername, boolean admin) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(subject)
                .issuer(ISSUER)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .claim(CLAIM_TYPE, TYPE_ACCESS)
                .claim(CLAIM_ROLES, admin ? List.of(ROLE_USER, ROLE_ADMIN) : List.of(ROLE_USER))
                .claim(CLAIM_SCOPE, admin ? SCOPE_CHAT + " " + SCOPE_ADMIN : SCOPE_CHAT)
                .claim(CLAIM_PREFERRED_USERNAME, preferredUsername)
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }

    /** Sign a refresh token. Public for tests. */
    public String issueRefreshToken(String subject) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(subject)
                .issuer(ISSUER)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(refreshTtl)))
                .id(UUID.randomUUID().toString())
                .claim(CLAIM_TYPE, TYPE_REFRESH)
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }

    @Override
    public UserId verifyRefreshToken(String refreshToken) {
        if (refreshToken == null || refreshToken.isBlank()) {
            throw new InvalidRefreshTokenException("missing token");
        }
        Claims claims;
        try {
            claims = Jwts.parser()
                    .verifyWith(key)
                    .requireIssuer(ISSUER)
                    .build()
                    .parseSignedClaims(refreshToken)
                    .getPayload();
        } catch (JwtException | IllegalArgumentException e) {
            throw new InvalidRefreshTokenException("signature, issuer or expiry check failed", e);
        }
        if (!TYPE_REFRESH.equals(claims.get(CLAIM_TYPE, String.class))) {
            throw new InvalidRefreshTokenException("not a refresh token");
        }
        if (claims.getExpiration() == null) {
            throw new InvalidRefreshTokenException("token has no expiry");
        }
        try {
            return UserId.from(claims.getSubject());
        } catch (RuntimeException e) {
            throw new InvalidRefreshTokenException("subject is not a user id", e);
        }
    }

    /** Whether the user's e-mail is on the {@code agentcook.auth.admins} list (exact match). */
    public boolean isAdmin(User user) {
        return adminEmails.contains(user.getEmail());
    }

    public long ttlSeconds() {
        return ttl.toSeconds();
    }

    public long refreshTtlSeconds() {
        return refreshTtl.toSeconds();
    }

    /**
     * Normalise each entry with the login rules so {@code admin} matches the
     * account created by registering {@code admin} ({@code admin@dev.local})
     * and e-mail entries are lower-cased like an e-mail login. Matching is
     * exact on the normalised form, so registering {@code Admin} (a
     * different bare username) does not inherit {@code admin}'s role.
     */
    private static Set<String> parseAdmins(String admins) {
        if (admins == null || admins.isBlank()) {
            return Set.of();
        }
        Set<String> emails = new LinkedHashSet<>();
        for (String entry : admins.split(",")) {
            if (entry.isBlank()) {
                continue;
            }
            try {
                emails.add(LoginIdentity.parse(entry).email());
            } catch (IllegalArgumentException e) {
                log.warn("Ignoring invalid agentcook.auth.admins entry '{}': {}", entry.trim(), e.getMessage());
            }
        }
        return Collections.unmodifiableSet(emails);
    }
}
