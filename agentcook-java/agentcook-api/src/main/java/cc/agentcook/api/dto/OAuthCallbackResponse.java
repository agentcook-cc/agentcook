package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "OAuth callback result. Phase 3 dev mode returns a dummy access token; Phase 4 swaps in a real one issued by the IM provider.")
public record OAuthCallbackResponse(

        @Schema(example = "dingtalk")
        String provider,

        @Schema(example = "dev-dingtalk-8aa3f6e6-3a9c-4f1f-9f1c-9f8b9c1d2e3f")
        String accessToken,

        @Schema(example = "Bearer", defaultValue = "Bearer")
        String tokenType,

        @Schema(example = "3600")
        long expiresIn
) {
}
