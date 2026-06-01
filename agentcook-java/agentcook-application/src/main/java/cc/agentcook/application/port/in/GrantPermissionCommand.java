package cc.agentcook.application.port.in;

import cc.agentcook.domain.permission.PermissionEffect;

import java.util.Objects;

public record GrantPermissionCommand(String userId, String resource, String action, PermissionEffect effect) {

    public GrantPermissionCommand {
        Objects.requireNonNull(userId, "userId must not be null");
        Objects.requireNonNull(resource, "resource must not be null");
        Objects.requireNonNull(action, "action must not be null");
        Objects.requireNonNull(effect, "effect must not be null");
    }
}
