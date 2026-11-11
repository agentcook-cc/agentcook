package cc.agentcook.application.port.in;

import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;

/**
 * Quota snapshot after a consume attempt.
 *
 * @param exhausted {@code true} when the user had no free questions left,
 *                  so nothing was consumed and the counters are unchanged
 *                  (ADR-018: the caller downgrades to the cheaper model
 *                  instead of blocking the user)
 */
public record QuotaConsumption(UserId userId, int used, int quota, int remaining, boolean exhausted) {

    public static QuotaConsumption of(User user, boolean exhausted) {
        return new QuotaConsumption(user.getId(), user.getFreeQuestionsUsed(),
                user.getFreeQuestionsQuota(), user.remainingFreeQuestions(), exhausted);
    }
}
