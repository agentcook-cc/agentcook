package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "OAuth callback payload posted by the IM provider after user authorization. Phase 3 dev profile only — Phase 4 hooks real provider SDKs.")
public record OAuthCallbackRequest(

        @Schema(example = "dingtalk", description = "IM provider id (dingtalk/feishu/telegram/discord/slack).")
        @NotBlank
        String provider,

        @Schema(example = "auth-code-from-provider")
        @NotBlank
        String code,

        @Schema(example = "csrf-state-token", description = "CSRF state token echoed back by the provider.")
        String state
) {
}
