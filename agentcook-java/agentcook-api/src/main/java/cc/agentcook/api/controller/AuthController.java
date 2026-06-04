package cc.agentcook.api.controller;

import cc.agentcook.api.auth.JwtTokenIssuer;
import cc.agentcook.api.auth.TurnstileVerifier;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.LoginRequest;
import cc.agentcook.api.dto.LoginResponse;
import cc.agentcook.application.port.in.CreateUserCommand;
import cc.agentcook.application.port.in.CreateUserUseCase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
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
 *
 * <p>W3 (Day 70+): JWT {@code sub} claim is the user's UUID, not the raw
 * username. Login auto-provisions a User aggregate keyed off
 * {@code <username>@dev.local} so {@code /api/v1/users/me} (and any other
 * UUID-keyed endpoint) can resolve the caller via SecurityContext without
 * a separate lookup table.</p>
 */
@RestController
@RequestMapping("/api/v1/auth")
@Tag(name = "Auth", description = "Authentication. Phase 3 issues HS256-signed JWTs against a dev secret.")
public class AuthController {

    private static final String DEV_EMAIL_DOMAIN = "@dev.local";

    private final JwtTokenIssuer tokenIssuer;
    private final TurnstileVerifier turnstileVerifier;
    private final UserRepository userRepository;
    private final CreateUserUseCase createUserUseCase;

    public AuthController(JwtTokenIssuer tokenIssuer,
                          TurnstileVerifier turnstileVerifier,
                          UserRepository userRepository,
                          CreateUserUseCase createUserUseCase) {
        this.tokenIssuer = tokenIssuer;
        this.turnstileVerifier = turnstileVerifier;
        this.userRepository = userRepository;
        this.createUserUseCase = createUserUseCase;
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
        UserId userId = resolveOrProvision(body.username());
        String token = tokenIssuer.issue(userId.value().toString());
        return ResponseEntity.ok(new LoginResponse(token, "Bearer", tokenIssuer.ttlSeconds()));
    }

    /**
     * Phase 3 dev placeholder: map {@code username} → User aggregate by
     * the synthesised email {@code <username>@dev.local}. If the user
     * does not exist yet, auto-provision one so the JWT subject is
     * always a real persisted UUID. Phase 4 swaps this for an IdP /
     * JWKS lookup keyed on the upstream issuer's subject claim.
     */
    private UserId resolveOrProvision(String username) {
        String email = username + DEV_EMAIL_DOMAIN;
        return userRepository.findByEmail(email)
                .map(User::getId)
                .orElseGet(() -> createUserUseCase.execute(new CreateUserCommand(email, username)));
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
