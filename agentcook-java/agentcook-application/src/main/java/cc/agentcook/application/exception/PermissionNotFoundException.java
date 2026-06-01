package cc.agentcook.application.exception;

import cc.agentcook.domain.permission.PermissionId;

public class PermissionNotFoundException extends RuntimeException {

    public PermissionNotFoundException(PermissionId permissionId) {
        super("Permission not found: " + permissionId);
    }
}
