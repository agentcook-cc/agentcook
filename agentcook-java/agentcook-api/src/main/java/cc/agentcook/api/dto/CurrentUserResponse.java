package cc.agentcook.api.dto;

import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserStatus;
import io.swagger.v3.oas.annotations.media.ArraySchema;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * {@code GET /api/v1/users/me}: the {@link UserResponse} fields plus the
 * roles carried by the caller's access token, so a console can decide
 * which views to show without decoding the JWT.
 */
@Schema(description = "The authenticated user and the roles of the presented access token.")
public record CurrentUserResponse(
        @Schema(format = "uuid") UUID id,
        String email,
        String nickname,
        UserStatus status,
        Instant createdAt,
        Instant updatedAt,

        @ArraySchema(schema = @Schema(example = "user"),
                arraySchema = @Schema(description = "`user`, plus `admin` for accounts listed in "
                        + "`agentcook.auth.admins` (decided when the token was issued)."))
        List<String> roles
) {
    public static CurrentUserResponse from(User user, List<String> roles) {
        return new CurrentUserResponse(
                user.getId().value(),
                user.getEmail(),
                user.getNickname(),
                user.getStatus(),
                user.getCreatedAt(),
                user.getUpdatedAt(),
                List.copyOf(roles));
    }
}
