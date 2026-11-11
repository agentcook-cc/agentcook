package cc.agentcook.application.port.in;

/**
 * Input Port: create an account with a password and sign it in.
 */
public interface RegisterUserUseCase {

    /** Shortest accepted password, in characters. */
    int MIN_PASSWORD_LENGTH = 8;

    /** Longest accepted password, in characters. */
    int MAX_PASSWORD_LENGTH = 128;

    /**
     * @throws cc.agentcook.application.exception.InvalidRegistrationException
     *         when the username or password violates the identity / length rules
     * @throws cc.agentcook.application.exception.UserAlreadyExistsException
     *         when the identity is already taken
     */
    AuthTokens execute(RegisterUserCommand command);
}
