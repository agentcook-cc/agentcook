package cc.agentcook.application.exception;

/**
 * Registration attempted for an identity that already has an account.
 */
public class UserAlreadyExistsException extends RuntimeException {

    public UserAlreadyExistsException(String username) {
        super("An account already exists for: " + username);
    }
}
