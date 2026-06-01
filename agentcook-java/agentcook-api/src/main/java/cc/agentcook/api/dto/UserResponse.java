package cc.agentcook.api.dto;

import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserStatus;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.UUID;

@Schema(description = "User aggregate snapshot.")
public record UserResponse(
        @Schema(format = "uuid") UUID id,
        String email,
        String nickname,
        UserStatus status,
        Instant createdAt,
        Instant updatedAt
) {
    public static UserResponse from(User user) {
        return new UserResponse(
                user.getId().value(),
                user.getEmail(),
                user.getNickname(),
                user.getStatus(),
                user.getCreatedAt(),
                user.getUpdatedAt());
    }
}
