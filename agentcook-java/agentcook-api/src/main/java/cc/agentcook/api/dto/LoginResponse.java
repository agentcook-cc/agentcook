package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "OAuth2-shaped token envelope. Phase 3 returns a dev dummy token; Phase 4 Day 31-32 swaps it for a signed JWT.")
public record LoginResponse(

        @Schema(example = "dev-token-alice")
        String accessToken,

        @Schema(example = "Bearer", defaultValue = "Bearer")
        String tokenType,

        @Schema(example = "3600", description = "Seconds until the token is no longer accepted.")
        long expiresIn
) {
}
