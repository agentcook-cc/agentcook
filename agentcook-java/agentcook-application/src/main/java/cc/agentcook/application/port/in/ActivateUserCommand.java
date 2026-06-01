package cc.agentcook.application.port.in;

import java.util.Objects;

public record ActivateUserCommand(String userId) {

    public ActivateUserCommand {
        Objects.requireNonNull(userId, "userId must not be null");
    }
}
