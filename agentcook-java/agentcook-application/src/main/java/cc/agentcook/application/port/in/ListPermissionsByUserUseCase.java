package cc.agentcook.application.port.in;

import cc.agentcook.domain.permission.Permission;

import java.util.List;

public interface ListPermissionsByUserUseCase {

    List<Permission> execute(ListPermissionsByUserQuery query);
}
