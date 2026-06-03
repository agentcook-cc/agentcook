package cc.agentcook.api.controller;

import cc.agentcook.api.auth.JwtTokenIssuer;
import cc.agentcook.api.auth.TurnstileVerifier;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.LoginRequest;
import cc.agentcook.api.dto.LoginResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Phase 3 development auth surface. As of Day 31 issues a real HS256
 * JWT (Phase 4 Day 33-34 swaps the dev secret for a real identity
 * issuer + JWKS).
 *
 * <p>The token shape stays stable across the swap — {@code accessToken}
 * / {@code tokenType: "Bearer"} / {@code expiresIn} (seconds) — so
 * frontend (Agent B) doesn't need to change anything.</p>
 */
@RestController
@RequestMapping("/api/v1/auth")
@Tag(name = "Auth", description = "Authentication. Phase 3 issues HS256-signed JWTs against a dev secret.")
public class AuthController {

    private final JwtTokenIssuer tokenIssuer;
    private final TurnstileVerifier turnstileVerifier;

    public AuthController(JwtTokenIssuer tokenIssuer, TurnstileVerifier turnstileVerifier) {
        this.tokenIssuer = tokenIssuer;
        this.turnstileVerifier = turnstileVerifier;
    }

    @PostMapping("/login")
    @Operation(summary = "Phase 3 dev login. Returns an HS256-signed JWT.")
    @ApiResponse(responseCode = "200", description = "Login accepted.",
            content = @Content(schema = @Schema(implementation = LoginResponse.class)))
    @ApiResponse(responseCode = "400", description = "Empty username or password.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "401",
            description = "Turnstile verification failed (only when `agentcook.turnstile.secret` is set).",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<LoginResponse> login(
            @Valid @RequestBody LoginRequest body,
            HttpServletRequest request) {
        if (body.password().isBlank() || body.username().isBlank()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).build();
        }
        // Buffer Day 62 / backlog #11 — gate login on Turnstile. Returns true
        // in dev mode (empty secret) so existing fixtures keep working.
        if (!turnstileVerifier.verify(body.turnstileToken(), clientIp(request))) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        String token = tokenIssuer.issue(body.username());
        return ResponseEntity.ok(new LoginResponse(token, "Bearer", tokenIssuer.ttlSeconds()));
    }

    /**
     * Prefer the first X-Forwarded-For hop when behind Cloudflare /
     * Traefik (both append the real client IP there). Falls back to
     * the socket-level remote address for direct connections.
     */
    private static String clientIp(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        if (xff != null && !xff.isBlank()) {
            int comma = xff.indexOf(',');
            return (comma < 0 ? xff : xff.substring(0, comma)).trim();
        }
        return request.getRemoteAddr();
    }
}
