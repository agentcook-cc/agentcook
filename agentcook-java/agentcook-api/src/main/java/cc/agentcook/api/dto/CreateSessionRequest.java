package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Payload to open a conversation session for an existing user. " +
        "When omitted, {@code userId} defaults to the JWT subject (the authenticated caller's UUID).")
public record CreateSessionRequest(

        @Schema(format = "uuid", example = "8aa3f6e6-3a9c-4f1f-9f1c-9f8b9c1d2e3f",
                description = "Owner UUID. Optional — falls back to the JWT subject when blank.",
                nullable = true)
        String userId,

        @Schema(example = "Trip planning")
        String title
) {
}
