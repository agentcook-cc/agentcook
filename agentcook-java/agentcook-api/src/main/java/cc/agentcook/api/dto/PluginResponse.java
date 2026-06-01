package cc.agentcook.api.dto;

import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginStatus;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.UUID;

@Schema(description = "Plugin aggregate snapshot.")
public record PluginResponse(
        @Schema(format = "uuid") UUID id,
        String name,
        String version,
        PluginKind kind,
        String description,
        PluginStatus status,
        Instant createdAt,
        Instant updatedAt
) {
    public static PluginResponse from(Plugin plugin) {
        return new PluginResponse(
                plugin.getId().value(),
                plugin.getName(),
                plugin.getVersion(),
                plugin.getKind(),
                plugin.getDescription(),
                plugin.getStatus(),
                plugin.getCreatedAt(),
                plugin.getUpdatedAt());
    }
}
