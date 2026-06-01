package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Admin payload to directly establish a Connector for an existing Plugin (bypasses end-user permission check).")
public record CreateConnectorRequest(

        @Schema(format = "uuid", example = "8aa3f6e6-3a9c-4f1f-9f1c-9f8b9c1d2e3f")
        @NotBlank
        String pluginId,

        @Schema(example = "{\"webhook_url\":\"https://example.com\"}")
        String connectorConfig
) {
}
