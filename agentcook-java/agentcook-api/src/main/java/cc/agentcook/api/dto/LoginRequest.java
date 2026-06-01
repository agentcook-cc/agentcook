package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Phase 3 dev login payload (Phase 4 Day 31-32 replaces with OAuth2 / B3 tokens).")
public record LoginRequest(

        @Schema(example = "alice")
        @NotBlank
        String username,

        @Schema(example = "dev")
        @NotBlank
        String password
) {
}
