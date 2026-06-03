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
        String password,

        @Schema(
                example = "0.cf-turnstile-response-token",
                description = "Cloudflare Turnstile response token (Buffer Day 62 / backlog #11). "
                        + "Required when `agentcook.turnstile.secret` is configured; ignored in "
                        + "dev mode when the secret is unset.",
                nullable = true)
        String turnstileToken
) {
}
