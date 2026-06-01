package cc.agentcook.api.dto;

import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionStatus;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;
import java.util.UUID;

@Schema(description = "Session aggregate snapshot.")
public record SessionResponse(
        @Schema(format = "uuid") UUID id,
        @Schema(format = "uuid") UUID userId,
        String title,
        SessionStatus status,
        Instant createdAt,
        Instant updatedAt
) {
    public static SessionResponse from(Session session) {
        return new SessionResponse(
                session.getId().value(),
                session.getUserId().value(),
                session.getTitle(),
                session.getStatus(),
                session.getCreatedAt(),
                session.getUpdatedAt());
    }
}
