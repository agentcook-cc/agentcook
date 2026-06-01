package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Payload to register a new user.")
public record CreateUserRequest(

        @Schema(example = "alice@example.com")
        @NotBlank @Email
        String email,

        @Schema(example = "Alice")
        String nickname
) {
}
