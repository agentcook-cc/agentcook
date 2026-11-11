package cc.agentcook.api.dto;

import cc.agentcook.application.port.in.RegisterUserUseCase;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

@Schema(description = "Self-service sign-up payload. On success the new user is signed in.")
public record RegisterRequest(

        @Schema(example = "alice",
                description = "E-mail address (stored lower-cased), or a bare username "
                        + "(3-32 of letters, digits, `_`, `.`, `-`) stored as `<username>@dev.local`.")
        @NotBlank
        String username,

        @Schema(example = "correct-horse-battery",
                minLength = RegisterUserUseCase.MIN_PASSWORD_LENGTH,
                maxLength = RegisterUserUseCase.MAX_PASSWORD_LENGTH)
        @NotBlank
        @Size(min = RegisterUserUseCase.MIN_PASSWORD_LENGTH, max = RegisterUserUseCase.MAX_PASSWORD_LENGTH)
        String password,

        @Schema(example = "Alice", nullable = true,
                description = "Display name; defaults to the username (or the e-mail's local part).")
        @Size(max = 255)
        String nickname,

        @Schema(example = "0.cf-turnstile-response-token", nullable = true,
                description = "Cloudflare Turnstile response token; required when "
                        + "`agentcook.turnstile.secret` is configured.")
        String turnstileToken
) {

    @Override
    public String toString() {
        return "RegisterRequest[username=" + username + ", nickname=" + nickname + "]";
    }
}
