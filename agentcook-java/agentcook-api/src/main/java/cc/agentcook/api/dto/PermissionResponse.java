package cc.agentcook.api.dto;

import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionEffect;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.UUID;

@Schema(description = "Permission aggregate snapshot.")
public record PermissionResponse(
        @Schema(format = "uuid") UUID id,
        @Schema(format = "uuid") UUID userId,
        String resource,
        String action,
        PermissionEffect effect,
        Instant createdAt
) {
    public static PermissionResponse from(Permission permission) {
        return new PermissionResponse(
                permission.getId().value(),
                permission.getUserId().value(),
                permission.getResource(),
                permission.getAction(),
                permission.getEffect(),
                permission.getCreatedAt());
    }
}
