package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.SuspendUserCommand;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import cc.agentcook.domain.user.UserStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SuspendUserUseCaseImplTest {

    @Mock private UserRepository userRepository;
    @InjectMocks private SuspendUserUseCaseImpl useCase;

    @Test
    void suspendsActiveUser() {
        UserId userId = UserId.generate();
        User active = User.reconstitute(userId, "u@x.com", "U",
                UserStatus.ACTIVE, Instant.now(), Instant.now());
        when(userRepository.findById(userId)).thenReturn(Optional.of(active));
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

        User suspended = useCase.execute(new SuspendUserCommand(userId.value().toString()));

        assertEquals(UserStatus.SUSPENDED, suspended.getStatus());
        verify(userRepository).save(active);
    }

    @Test
    void rejectsUnknownUserId() {
        UserId userId = UserId.from(UUID.randomUUID());
        when(userRepository.findById(userId)).thenReturn(Optional.empty());

        assertThrows(UserNotFoundException.class,
                () -> useCase.execute(new SuspendUserCommand(userId.value().toString())));

        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void rejectsSuspendingDeletedUserPerDomainInvariant() {
        UserId userId = UserId.generate();
        User deleted = User.reconstitute(userId, "u@x.com", "U",
                UserStatus.DELETED, Instant.now(), Instant.now());
        when(userRepository.findById(userId)).thenReturn(Optional.of(deleted));

        assertThrows(IllegalStateException.class,
                () -> useCase.execute(new SuspendUserCommand(userId.value().toString())));

        verify(userRepository, never()).save(any(User.class));
    }
}
