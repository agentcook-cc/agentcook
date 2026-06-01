package cc.agentcook.application.port.in;

import java.util.Objects;

public record CreateUserCommand(String email, String nickname) {

    public CreateUserCommand {
        Objects.requireNonNull(email, "email must not be null");
    }
}
