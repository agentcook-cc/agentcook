package cc.agentcook.api.controller;

import cc.agentcook.api.auth.TurnstileRejectedException;
import cc.agentcook.api.auth.TurnstileVerifier;
import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.LoginRequest;
import cc.agentcook.api.dto.LoginResponse;
import cc.agentcook.api.dto.RefreshTokenRequest;
import cc.agentcook.api.dto.RegisterRequest;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.in.LoginCommand;
import cc.agentcook.application.port.in.LoginUseCase;
import cc.agentcook.application.port.in.RefreshTokenCommand;
import cc.agentcook.application.port.in.RefreshTokenUseCase;
import cc.agentcook.application.port.in.RegisterUserCommand;
import cc.agentcook.application.port.in.RegisterUserUseCase;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;

/**
 * Password authentication. All three endpoints are public and return the
 * same {@link LoginResponse} token envelope: a short-lived access JWT
 * ({@code sub} = user UUID, so {@code /api/v1/users/me} and every other
 * UUID-keyed endpoint resolve the caller from the SecurityContext) and a
 * long-lived refresh JWT.
 *
 * <p>Error contract ({@link ApiError} bodies): {@code AUTH_INVALID_CREDENTIALS}
 * (401, identical for unknown user / wrong password / no password set),
 * {@code AUTH_ACCOUNT_DISABLED} (403), {@code AUTH_USER_EXISTS} (409),
 * {@code AUTH_INVALID_REFRESH_TOKEN} (401), {@code TURNSTILE_REJECTED}
 * (401) and {@code VALIDATION_FAILED} (400).</p>
 *
 * <p>A bearer header sent to these endpoints is ignored (see
 * {@link cc.agentcook.api.config.SecurityConfig}), so a client with an
 * expired access token can still log in or refresh.</p>
 */
@RestController
@RequestMapping("/api/v1/auth")
@Tag(name = "Auth", description = "Password authentication: register, login, refresh. Issues HS256-signed JWTs.")
@SecurityRequirements
public class AuthController {

    private final TurnstileVerifier turnstileVerifier;
    private final LoginUseCase loginUseCase;
    private final RegisterUserUseCase registerUserUseCase;
    private final RefreshTokenUseCase refreshTokenUseCase;

    public AuthController(TurnstileVerifier turnstileVerifier,
                          LoginUseCase loginUseCase,
                          RegisterUserUseCase registerUserUseCase,
                          RefreshTokenUseCase refreshTokenUseCase) {
        this.turnstileVerifier = turnstileVerifier;
        this.loginUseCase = loginUseCase;
        this.registerUserUseCase = registerUserUseCase;
        this.refreshTokenUseCase = refreshTokenUseCase;
    }

    @PostMapping("/login")
    @Operation(summary = "Log in with username (or e-mail) and password.",
            description = "Unknown users are rejected unless `agentcook.auth.auto-provision` is on "
                    + "(dev profile), in which case the account is created with this password. Accounts "
                    + "without a password (seed data, pre-password rows) are claimed by their first "
                    + "login only under auto-provision.")
    @ApiResponse(responseCode = "200", description = "Login accepted.",
            content = @Content(schema = @Schema(implementation = LoginResponse.class)))
    @ApiResponse(responseCode = "400", description = "VALIDATION_FAILED — blank username or password.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "401",
            description = "AUTH_INVALID_CREDENTIALS, or TURNSTILE_REJECTED "
                    + "(only when `agentcook.turnstile.secret` is set).",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "403", description = "AUTH_ACCOUNT_DISABLED — correct password, suspended account.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<LoginResponse> login(
            @Valid @RequestBody LoginRequest body,
            HttpServletRequest request) {
        // Buffer Day 62 / backlog #11 — gate login on Turnstile. Returns true
        // in dev mode (empty secret) so existing fixtures keep working.
        requireHuman(body.turnstileToken(), request);
        AuthTokens tokens = loginUseCase.execute(new LoginCommand(body.username(), body.password()));
        return ResponseEntity.ok(LoginResponse.from(tokens));
    }

    @PostMapping("/register")
    @Operation(summary = "Create an account with a password and log it in.")
    @ApiResponse(responseCode = "201", description = "Account created; tokens issued.",
            content = @Content(schema = @Schema(implementation = LoginResponse.class)))
    @ApiResponse(responseCode = "400",
            description = "VALIDATION_FAILED — bad username format, password outside 8-128 "
                    + "characters, or malformed JSON.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "401", description = "TURNSTILE_REJECTED — Turnstile verification failed.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "409", description = "AUTH_USER_EXISTS — the identity already has an account.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<LoginResponse> register(
            @Valid @RequestBody RegisterRequest body,
            HttpServletRequest request) {
        requireHuman(body.turnstileToken(), request);
        AuthTokens tokens = registerUserUseCase.execute(
                new RegisterUserCommand(body.username(), body.password(), body.nickname()));
        return ResponseEntity.created(URI.create("/api/v1/users/me")).body(LoginResponse.from(tokens));
    }

    @PostMapping("/refresh")
    @Operation(summary = "Exchange a refresh token for a new access + refresh token pair.",
            description = "Access tokens are refused here and refresh tokens are refused everywhere else.")
    @ApiResponse(responseCode = "200", description = "New token pair issued.",
            content = @Content(schema = @Schema(implementation = LoginResponse.class)))
    @ApiResponse(responseCode = "400", description = "VALIDATION_FAILED — missing refreshToken.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    @ApiResponse(responseCode = "401",
            description = "AUTH_INVALID_REFRESH_TOKEN — invalid, expired, not a refresh token, or the "
                    + "user is gone / not active.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<LoginResponse> refresh(@Valid @RequestBody RefreshTokenRequest body) {
        AuthTokens tokens = refreshTokenUseCase.execute(new RefreshTokenCommand(body.refreshToken()));
        return ResponseEntity.ok(LoginResponse.from(tokens));
    }

    private void requireHuman(String turnstileToken, HttpServletRequest request) {
        if (!turnstileVerifier.verify(turnstileToken, clientIp(request))) {
            throw new TurnstileRejectedException();
        }
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
