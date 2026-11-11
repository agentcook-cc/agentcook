package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.AccountDisabledException;
import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.ConsumeQuotaCommand;
import cc.agentcook.application.port.in.ConsumeQuotaUseCase;
import cc.agentcook.application.port.in.QuotaConsumption;
import cc.agentcook.domain.user.QuotaExhaustedException;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Consume one free-tier question (ADR-018).
 *
 * <p><b>Concurrency:</b> two chat turns finishing at the same time both
 * call this. The user row is loaded with
 * {@link UserRepository#findByIdForUpdate} ({@code SELECT … FOR UPDATE}),
 * so the second transaction waits for the first to commit and then sees
 * its increment — the classic lost update (both read {@code used=1},
 * both write {@code used=2}) cannot happen, and the domain check in
 * {@link User#consumeFreeQuestion()} always runs against the committed
 * counter. The other read-modify-write use cases on User take the same
 * lock, so e.g. a concurrent profile update cannot write a stale counter
 * back either.</p>
 *
 * <p>An exhausted quota is a normal outcome, not an error: the result
 * says {@code exhausted=true} and nothing is written.</p>
 */
@Service
@Transactional
public class ConsumeQuotaUseCaseImpl implements ConsumeQuotaUseCase {

    private final UserRepository userRepository;

    public ConsumeQuotaUseCaseImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public QuotaConsumption execute(ConsumeQuotaCommand command) {
        UserId userId = UserId.from(command.userId());
        User user = userRepository.findByIdForUpdate(userId)
                .orElseThrow(() -> new UserNotFoundException(userId));
        if (!user.isActive()) {
            throw new AccountDisabledException(user.getStatus());
        }
        try {
            user.consumeFreeQuestion();
        } catch (QuotaExhaustedException exhausted) {
            return QuotaConsumption.of(user, true);
        }
        return QuotaConsumption.of(userRepository.save(user), false);
    }
}
