package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Updates a Connector's configuration JSON without changing its status.")
public record UpdateConnectorConfigRequest(

        @Schema(example = "{\"webhook_url\":\"https://example.com/v2\"}")
        String config
) {
}
