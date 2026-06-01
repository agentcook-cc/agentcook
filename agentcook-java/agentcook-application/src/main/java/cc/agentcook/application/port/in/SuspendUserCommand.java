package cc.agentcook.application.port.in;

import java.util.Objects;

public record SuspendUserCommand(String userId) {

    public SuspendUserCommand {
        Objects.requireNonNull(userId, "userId must not be null");
    }
}
