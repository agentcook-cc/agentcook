package cc.agentcook.api.controller;

import cc.agentcook.api.dto.ApiError;
import cc.agentcook.api.dto.OAuthCallbackRequest;
import cc.agentcook.api.dto.OAuthCallbackResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Set;
import java.util.UUID;

/**
 * Phase 3 OAuth callback handler. The frontend (Agent B) uses this
 * dummy implementation to wire up its OAuthFlow component end-to-end
 * without depending on a real IM provider's authorization server.
 *
 * <p>Phase 4 (Day 33-34 per agent-d-java-architect.md) replaces the
 * dummy with real DingTalk / Feishu / Telegram / Discord / Slack SDK
 * exchanges. The wire shape ({@code provider/code/state} →
 * {@code accessToken/tokenType/expiresIn}) is stable across that swap.</p>
 */
@RestController
@RequestMapping("/api/v1/connectors/oauth")
@Tag(name = "Connectors-OAuth", description = "OAuth callback for IM provider authorization (Phase 3 dev dummy).")
public class OAuthCallbackController {

    private static final Set<String> SUPPORTED_PROVIDERS = Set.of(
            "dingtalk", "feishu", "telegram", "discord", "slack");

    private static final long DEV_TOKEN_TTL_SECONDS = 3600L;

    @PostMapping("/callback")
    @Operation(summary = "Receive an OAuth authorization-code callback. Phase 3 returns a dummy bearer token.")
    @ApiResponse(responseCode = "200", description = "Token issued.",
            content = @Content(schema = @Schema(implementation = OAuthCallbackResponse.class)))
    @ApiResponse(responseCode = "400", description = "Unsupported provider or malformed payload.",
            content = @Content(schema = @Schema(implementation = ApiError.class)))
    public ResponseEntity<OAuthCallbackResponse> callback(@Valid @RequestBody OAuthCallbackRequest body) {
        if (!SUPPORTED_PROVIDERS.contains(body.provider())) {
            return ResponseEntity.badRequest().build();
        }
        String accessToken = "dev-" + body.provider() + "-" + UUID.randomUUID();
        return ResponseEntity.ok(new OAuthCallbackResponse(
                body.provider(), accessToken, "Bearer", DEV_TOKEN_TTL_SECONDS));
    }
}
