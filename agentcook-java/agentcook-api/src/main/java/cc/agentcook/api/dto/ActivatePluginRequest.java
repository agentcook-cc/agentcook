package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Payload to activate a plugin for a user, establishing a Connector.")
public record ActivatePluginRequest(

        @Schema(format = "uuid", example = "8aa3f6e6-3a9c-4f1f-9f1c-9f8b9c1d2e3f")
        @NotBlank
        String userId,

        @Schema(example = "{\"webhook_url\":\"https://example.com/webhook\"}")
        String connectorConfig
) {
}
