package cc.agentcook.api.dto;

import cc.agentcook.application.port.in.PingConnectorResult;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Result of a Connector ping. Phase 3 returns mock latency; Phase 4 swaps in real upstream IM SDK calls.")
public record ConnectorPingResponse(
        @Schema(example = "CONNECTED") String status,
        @Schema(example = "42") long latencyMs
) {
    public static ConnectorPingResponse from(PingConnectorResult result) {
        return new ConnectorPingResponse(result.status().name(), result.latencyMs());
    }
}
