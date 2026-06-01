package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Payload to open a conversation session for an existing user.")
public record CreateSessionRequest(

        @Schema(format = "uuid", example = "8aa3f6e6-3a9c-4f1f-9f1c-9f8b9c1d2e3f")
        @NotBlank
        String userId,

        @Schema(example = "Trip planning")
        String title
) {
}
