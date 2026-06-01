package cc.agentcook.application.port.in;

import java.util.Objects;

public record UpdateSessionCommand(String sessionId, String title) {

    public UpdateSessionCommand {
        Objects.requireNonNull(sessionId, "sessionId must not be null");
    }
}
