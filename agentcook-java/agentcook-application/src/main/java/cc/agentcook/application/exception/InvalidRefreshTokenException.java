package cc.agentcook.application.exception;

/**
 * A refresh token was rejected: bad signature / issuer, expired, not a
 * refresh token, or its user is gone or no longer active.
 */
public class InvalidRefreshTokenException extends RuntimeException {

    public InvalidRefreshTokenException(String reason) {
        super("Invalid refresh token: " + reason);
    }

    public InvalidRefreshTokenException(String reason, Throwable cause) {
        super("Invalid refresh token: " + reason, cause);
    }
}
