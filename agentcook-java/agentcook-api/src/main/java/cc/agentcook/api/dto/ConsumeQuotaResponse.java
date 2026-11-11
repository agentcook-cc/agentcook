package cc.agentcook.api.dto;

import cc.agentcook.application.port.in.QuotaConsumption;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.UUID;

/**
 * Quota snapshot after {@code POST /api/v1/quota/consume} (ADR-018).
 */
@Schema(description = "Free-tier quota state after recording one chat turn.")
public record ConsumeQuotaResponse(
        @Schema(format = "uuid", description = "User aggregate id.")
        UUID userId,

        @Schema(example = "2", description = "Free-tier questions consumed so far (after this call).")
        int used,

        @Schema(example = "2", description = "Per-user quota ceiling.")
        int quota,

        @Schema(example = "0", description = "Free questions still available (quota - used, clamped to 0).")
        int remaining,

        @Schema(example = "false",
                description = "true when the quota was already used up, so nothing was consumed and the "
                        + "counters are unchanged. Not an error: the runtime downgrades to the cheaper "
                        + "model instead of blocking the user.")
        boolean exhausted
) {
    public static ConsumeQuotaResponse from(QuotaConsumption consumption) {
        return new ConsumeQuotaResponse(
                consumption.userId().value(),
                consumption.used(),
                consumption.quota(),
                consumption.remaining(),
                consumption.exhausted());
    }
}
