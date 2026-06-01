package cc.agentcook.application.port.in;

import cc.agentcook.domain.permission.Permission;

/**
 * Input Port: grant or deny a permission to a user. The {@code effect}
 * field on the command picks {@link cc.agentcook.domain.permission.Permission#grant}
 * vs {@link cc.agentcook.domain.permission.Permission#deny}.
 */
public interface GrantPermissionUseCase {

    Permission execute(GrantPermissionCommand command);
}
