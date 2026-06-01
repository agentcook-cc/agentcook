package cc.agentcook.application.port.in;

import java.util.Objects;

public record RevokePermissionCommand(String permissionId) {

    public RevokePermissionCommand {
        Objects.requireNonNull(permissionId, "permissionId must not be null");
    }
}
