package cc.agentcook.api.dto;

import cc.agentcook.domain.permission.PermissionEffect;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

@Schema(description = "Payload to grant or deny a permission to a user.")
public record GrantPermissionRequest(

        @Schema(example = "plugin:dingtalk")
        @NotBlank
        String resource,

        @Schema(example = "activate")
        @NotBlank
        String action,

        @Schema(example = "ALLOW")
        @NotNull
        PermissionEffect effect
) {
}
