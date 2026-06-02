package cc.agentcook.api.dto;

import cc.agentcook.domain.user.User;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.UUID;

/**
 * Chat quota snapshot for the calling user (ADR-018 §1).
 *
 * <p>The Python middleware (`middleware/quota.py`) reads this on every
 * chat request to decide whether to route to qwen-turbo (under quota)
 * or downgrade to glm-4-flash (over quota) — see ADR-018 §4 "代码改动
 * 范围" for the cross-language seam.</p>
 */
@Schema(description = "Per-user free-tier chat quota state (ADR-018 v1).")
public record QuotaResponse(
        @Schema(format = "uuid", description = "User aggregate id.")
        UUID userId,

        @Schema(example = "1",
                description = "Free-tier questions consumed so far.")
        int used,

        @Schema(example = "2",
                description = "Per-user quota ceiling (v1 default 2).")
        int quota,

        @Schema(example = "1",
                description = "Free questions still available "
                        + "(quota - used, clamped to 0).")
        int remaining
) {
    public static QuotaResponse from(User user) {
        return new QuotaResponse(
                user.getId().value(),
                user.getFreeQuestionsUsed(),
                user.getFreeQuestionsQuota(),
                user.remainingFreeQuestions());
    }
}
