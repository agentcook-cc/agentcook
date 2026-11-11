package cc.agentcook.application.port.in;

/**
 * Input Port: verify a username / password and issue tokens.
 *
 * <p>Every credential failure (unknown user, wrong password, account
 * without a password) surfaces as the same
 * {@link cc.agentcook.application.exception.InvalidCredentialsException}
 * so callers cannot probe which identities exist.</p>
 */
public interface LoginUseCase {

    /**
     * @throws cc.agentcook.application.exception.InvalidCredentialsException
     *         when the credentials do not authenticate a user
     * @throws cc.agentcook.application.exception.AccountDisabledException
     *         when the credentials are right but the account is not active
     */
    AuthTokens execute(LoginCommand command);
}
