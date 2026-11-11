package cc.agentcook.api.exception;

/**
 * The access token is valid but its {@code sub} is not a user id, so the
 * caller owns nothing. Answered like any unknown user: 404
 * {@code USER_NOT_FOUND}.
 */
public class UnknownSubjectException extends RuntimeException {

    public UnknownSubjectException() {
        super("The token subject does not identify a user");
    }
}
