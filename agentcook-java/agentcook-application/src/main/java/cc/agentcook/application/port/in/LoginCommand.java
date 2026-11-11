package cc.agentcook.application.port.in;

import java.util.Objects;

/**
 * Password login.
 *
 * @param username e-mail address or bare username (see {@code LoginIdentity})
 * @param password raw password to verify
 */
public record LoginCommand(String username, String password) {

    public LoginCommand {
        Objects.requireNonNull(username, "username must not be null");
        Objects.requireNonNull(password, "password must not be null");
    }

    @Override
    public String toString() {
        return "LoginCommand[username=" + username + "]";
    }
}
