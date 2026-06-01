package cc.agentcook.application.port.in;

import java.util.Objects;

public record CreateSessionCommand(String userId, String title) {

    public CreateSessionCommand {
        Objects.requireNonNull(userId, "userId must not be null");
    }
}
