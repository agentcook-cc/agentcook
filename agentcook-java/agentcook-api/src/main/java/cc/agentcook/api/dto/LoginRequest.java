package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Password login payload.")
public record LoginRequest(

        @Schema(example = "alice",
                description = "E-mail address, or a bare username (3-32 of letters, digits, `_`, `.`, `-`) "
                        + "which is the account `<username>@dev.local`.")
        @NotBlank
        String username,

        @Schema(example = "correct-horse-battery")
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

    @Override
    public String toString() {
        return "LoginRequest[username=" + username + "]";
    }
}
