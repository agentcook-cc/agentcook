package cc.agentcook.application.exception;

/**
 * Login failed. Deliberately carries no detail about <em>why</em>
 * (unknown user / wrong password / no password set) so the HTTP layer
 * returns one indistinguishable 401 for all of them.
 */
public class InvalidCredentialsException extends RuntimeException {

    public InvalidCredentialsException() {
        super("Invalid username or password");
    }
}
