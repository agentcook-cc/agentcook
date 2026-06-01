package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.GrantPermissionCommand;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionEffect;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.user.UserId;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class GrantPermissionUseCaseImplTest {

    @Mock private PermissionRepository permissionRepository;
    @InjectMocks private GrantPermissionUseCaseImpl useCase;

    @Test
    void grantsAllowPermission() {
        UserId userId = UserId.generate();
        when(permissionRepository.save(any(Permission.class))).thenAnswer(inv -> inv.getArgument(0));

        Permission permission = useCase.execute(new GrantPermissionCommand(
                userId.value().toString(), "plugin:dingtalk", "activate", PermissionEffect.ALLOW));

        assertTrue(permission.isAllowed());
        assertEquals(userId, permission.getUserId());
    }

    @Test
    void grantsDenyPermission() {
        UserId userId = UserId.generate();
        when(permissionRepository.save(any(Permission.class))).thenAnswer(inv -> inv.getArgument(0));

        Permission permission = useCase.execute(new GrantPermissionCommand(
                userId.value().toString(), "plugin:feishu", "activate", PermissionEffect.DENY));

        assertEquals(PermissionEffect.DENY, permission.getEffect());
    }

    @Test
    void rejectsMalformedUserIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new GrantPermissionCommand(
                        "not-a-uuid", "r", "a", PermissionEffect.ALLOW)));

        verify(permissionRepository, never()).save(any(Permission.class));
    }
}
