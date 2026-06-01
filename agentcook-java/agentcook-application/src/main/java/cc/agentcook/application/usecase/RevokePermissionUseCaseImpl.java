package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PermissionNotFoundException;
import cc.agentcook.application.port.in.RevokePermissionCommand;
import cc.agentcook.application.port.in.RevokePermissionUseCase;
import cc.agentcook.domain.permission.PermissionId;
import cc.agentcook.domain.permission.PermissionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class RevokePermissionUseCaseImpl implements RevokePermissionUseCase {

    private final PermissionRepository permissionRepository;

    public RevokePermissionUseCaseImpl(PermissionRepository permissionRepository) {
        this.permissionRepository = permissionRepository;
    }

    @Override
    public void execute(RevokePermissionCommand command) {
        PermissionId permissionId = PermissionId.from(command.permissionId());
        if (permissionRepository.findById(permissionId).isEmpty()) {
            throw new PermissionNotFoundException(permissionId);
        }
        permissionRepository.delete(permissionId);
    }
}
