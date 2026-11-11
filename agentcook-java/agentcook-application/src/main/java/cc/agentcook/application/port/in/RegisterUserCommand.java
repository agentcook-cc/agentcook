package cc.agentcook.application.port.in;

import java.util.Objects;

/**
 * Self-service sign-up.
 *
 * @param username e-mail address or bare username (see {@code LoginIdentity})
 * @param password raw password; hashed by the use case, never stored
 * @param nickname optional display name (defaults to the username)
 */
public record RegisterUserCommand(String username, String password, String nickname) {

    public RegisterUserCommand {
        Objects.requireNonNull(username, "username must not be null");
        Objects.requireNonNull(password, "password must not be null");
    }

    @Override
    public String toString() {
        return "RegisterUserCommand[username=" + username + ", nickname=" + nickname + "]";
    }
}
