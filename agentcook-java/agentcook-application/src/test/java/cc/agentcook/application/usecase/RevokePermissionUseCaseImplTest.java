package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.PermissionNotFoundException;
import cc.agentcook.application.port.in.RevokePermissionCommand;
import cc.agentcook.domain.permission.Permission;
import cc.agentcook.domain.permission.PermissionId;
import cc.agentcook.domain.permission.PermissionRepository;
import cc.agentcook.domain.user.UserId;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RevokePermissionUseCaseImplTest {

    @Mock private PermissionRepository permissionRepository;
    @InjectMocks private RevokePermissionUseCaseImpl useCase;

    @Test
    void revokesExistingPermission() {
        Permission existing = Permission.grant(UserId.generate(), "r", "a");
        when(permissionRepository.findById(existing.getId())).thenReturn(Optional.of(existing));

        useCase.execute(new RevokePermissionCommand(existing.getId().value().toString()));

        verify(permissionRepository).delete(existing.getId());
    }

    @Test
    void rejectsUnknownPermissionId() {
        PermissionId permissionId = PermissionId.from(UUID.randomUUID());
        when(permissionRepository.findById(permissionId)).thenReturn(Optional.empty());

        assertThrows(PermissionNotFoundException.class,
                () -> useCase.execute(new RevokePermissionCommand(permissionId.value().toString())));

        verify(permissionRepository, never()).delete(permissionId);
    }

    @Test
    void rejectsMalformedPermissionIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new RevokePermissionCommand("not-a-uuid")));

        verify(permissionRepository, never()).delete(org.mockito.ArgumentMatchers.any());
    }
}
