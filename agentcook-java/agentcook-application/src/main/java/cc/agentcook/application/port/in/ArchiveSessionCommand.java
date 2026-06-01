package cc.agentcook.application.port.in;

import java.util.Objects;

public record ArchiveSessionCommand(String sessionId) {

    public ArchiveSessionCommand {
        Objects.requireNonNull(sessionId, "sessionId must not be null");
    }
}
