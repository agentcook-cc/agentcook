package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.GrantPermissionCommand;
import cc.agentcook.application.port.in.GrantPermissionUseCase;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionEffect;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.user.UserId;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class GrantPermissionUseCaseImpl implements GrantPermissionUseCase {

    private final PermissionRepository permissionRepository;

    public GrantPermissionUseCaseImpl(PermissionRepository permissionRepository) {
        this.permissionRepository = permissionRepository;
    }

    @Override
    public Permission execute(GrantPermissionCommand command) {
        UserId userId = UserId.from(command.userId());
        Permission permission = command.effect() == PermissionEffect.ALLOW
                ? Permission.grant(userId, command.resource(), command.action())
                : Permission.deny(userId, command.resource(), command.action());
        return permissionRepository.save(permission);
    }
}
