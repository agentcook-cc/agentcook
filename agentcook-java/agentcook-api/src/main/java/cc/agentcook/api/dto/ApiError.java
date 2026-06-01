package cc.agentcook.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Flat error envelope. Field names match frontend-conventions §7.6 (B canonical).")
public record ApiError(

        @Schema(example = "DUPLICATE_EMAIL")
        String code,

        @Schema(example = "User already exists with email: alice@example.com")
        String message
) {
}
