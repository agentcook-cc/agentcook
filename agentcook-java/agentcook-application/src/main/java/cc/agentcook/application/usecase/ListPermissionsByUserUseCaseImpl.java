package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListPermissionsByUserQuery;
import cc.agentcook.application.port.in.ListPermissionsByUserUseCase;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.user.UserId;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ListPermissionsByUserUseCaseImpl implements ListPermissionsByUserUseCase {

    private final PermissionRepository permissionRepository;

    public ListPermissionsByUserUseCaseImpl(PermissionRepository permissionRepository) {
        this.permissionRepository = permissionRepository;
    }

    @Override
    public List<Permission> execute(ListPermissionsByUserQuery query) {
        UserId userId = UserId.from(query.userId());
        return permissionRepository.findByUserId(userId);
    }
}
