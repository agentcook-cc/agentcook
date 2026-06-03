package cc.agentcook.api.controller;

import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.QuotaResponse;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/**
 * Read-only quota endpoint for the chat plane. The Python middleware
 * (`agentcook/src/agentcook_app/middleware/quota.py`) calls this on
 * every chat request to decide whether to route to the qwen-turbo
 * default or downgrade to glm-4-flash (ADR-018 §2).
 *
 * <p>The JWT subject (sub claim) is the user's UUID — set when
 * `AuthController.login` issued the token. Phase 4 Day 33-34 will
 * swap that for an external IdP subject, at which point a lookup
 * table will sit between sub and {@link UserId}; for v1 the seam is
 * a straight {@code UUID.fromString(sub)} call.</p>
 */
@RestController
@RequestMapping("/api/v1/quota")
@Tag(name = "Quota", description = "Chat quota state (ADR-018).")
public class QuotaController {

    private final UserRepository userRepository;

    public QuotaController(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @GetMapping
    @Operation(summary = "Get the calling user's chat quota state.",
            security = @SecurityRequirement(name = "bearerAuth"))
    @ApiResponse(responseCode = "200", description = "Current quota snapshot.",
            content = @Content(schema = @Schema(implementation = QuotaResponse.class)))
    @ApiResponse(responseCode = "401", description = "Missing or invalid Bearer token.")
    @ApiResponse(responseCode = "404", description = "JWT subject does not resolve to a known user.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<QuotaResponse> getQuota(@AuthenticationPrincipal Jwt jwt) {
        // JWT subject (sub claim) is the user UUID. Phase 4 Day 33-34
        // adds an IdP-sub → UserId lookup; until then it's a direct
        // UUID parse + repository lookup.
        //
        // In production, jwt is never null — the OAuth2 Resource Server
        // filter rejects unauthenticated requests at 401 before they
        // reach the controller. Under test profiles that use a permitAll
        // SecurityFilterChain (the shared ApiIntegrationTestBase), jwt
        // can be null; we treat that the same as "sub does not resolve
        // to a user" and return 404.
        if (jwt == null || jwt.getSubject() == null) {
            return ResponseEntity.notFound().build();
        }
        UserId userId;
        try {
            userId = UserId.from(UUID.fromString(jwt.getSubject()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.notFound().build();
        }

        User user = userRepository.findById(userId).orElse(null);
        if (user == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(QuotaResponse.from(user));
    }
}
