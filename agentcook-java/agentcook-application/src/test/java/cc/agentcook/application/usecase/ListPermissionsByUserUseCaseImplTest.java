package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListPermissionsByUserQuery;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.user.UserId;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ListPermissionsByUserUseCaseImplTest {

    @Mock private PermissionRepository permissionRepository;
    @InjectMocks private ListPermissionsByUserUseCaseImpl useCase;

    @Test
    void listsPermissionsForUser() {
        UserId userId = UserId.generate();
        when(permissionRepository.findByUserId(userId)).thenReturn(List.of(
                Permission.grant(userId, "plugin:dingtalk", "activate"),
                Permission.deny(userId, "plugin:feishu", "activate")));

        List<Permission> permissions = useCase.execute(new ListPermissionsByUserQuery(userId.value().toString()));

        assertEquals(2, permissions.size());
    }

    @Test
    void returnsEmptyListWhenUserHasNoPermissions() {
        UserId userId = UserId.from(UUID.randomUUID());
        when(permissionRepository.findByUserId(userId)).thenReturn(List.of());

        List<Permission> permissions = useCase.execute(new ListPermissionsByUserQuery(userId.value().toString()));

        assertEquals(0, permissions.size());
    }

    @Test
    void rejectsMalformedUserIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new ListPermissionsByUserQuery("not-a-uuid")));

        verify(permissionRepository, never()).findByUserId(org.mockito.ArgumentMatchers.any());
    }
}
