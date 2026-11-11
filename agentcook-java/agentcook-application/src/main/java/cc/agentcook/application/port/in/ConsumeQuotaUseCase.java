package cc.agentcook.application.port.in;

/**
 * Input Port: consume one free-tier question for the caller (ADR-018).
 * Called by the Python runtime after each completed chat turn.
 */
public interface ConsumeQuotaUseCase {

    /**
     * Never fails because the quota is used up — that case returns
     * {@link QuotaConsumption#exhausted()} {@code = true}.
     *
     * @throws cc.agentcook.application.exception.UserNotFoundException
     *         when the user does not exist
     * @throws cc.agentcook.application.exception.AccountDisabledException
     *         when the account is not active
     */
    QuotaConsumption execute(ConsumeQuotaCommand command);
}
