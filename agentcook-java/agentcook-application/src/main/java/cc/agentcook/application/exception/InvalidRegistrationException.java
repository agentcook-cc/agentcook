package cc.agentcook.application.exception;

/**
 * Registration input violates the identity or password rules. The message
 * is {@code "<field>: <reason>"}, the same shape the API layer uses for
 * bean-validation failures, so both surface as one 400 error code.
 */
public class InvalidRegistrationException extends IllegalArgumentException {

    public InvalidRegistrationException(String field, String reason) {
        super(field + ": " + reason);
    }
}
