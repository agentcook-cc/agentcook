package cc.agentcook.api.dto;

import cc.agentcook.domain.connector.Connector;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.UUID;

@Schema(description = "Connector aggregate snapshot returned by activate-plugin.")
public record ConnectorResponse(
        @Schema(format = "uuid") UUID id,
        @Schema(format = "uuid") UUID pluginId,
        String status
) {
    public static ConnectorResponse from(Connector connector) {
        return new ConnectorResponse(
                connector.getId().value(),
                connector.getPluginId().value(),
                connector.getStatus().name());
    }
}
