package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Update a user's profile.")
public record UpdateUserRequest(
        @NotBlank @Schema(description = "New nickname.") String nickname
) {
}
