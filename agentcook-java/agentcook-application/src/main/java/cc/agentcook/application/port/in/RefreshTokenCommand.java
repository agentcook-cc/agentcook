package cc.agentcook.application.port.in;

import java.util.Objects;

public record RefreshTokenCommand(String refreshToken) {

    public RefreshTokenCommand {
        Objects.requireNonNull(refreshToken, "refreshToken must not be null");
    }

    @Override
    public String toString() {
        return "RefreshTokenCommand[refreshToken=<redacted>]";
    }
}
