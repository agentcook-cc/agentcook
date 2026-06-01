package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.UpdateUserCommand;
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
class UpdateUserUseCaseImplTest {

    @Mock private UserRepository userRepository;
    @InjectMocks private UpdateUserUseCaseImpl useCase;

    @Test
    void updatesNicknameOfExistingUser() {
        UserId userId = UserId.generate();
        User existing = User.reconstitute(
                userId, "alice@example.com", "Alice",
                UserStatus.ACTIVE, Instant.now(), Instant.now());
        when(userRepository.findById(userId)).thenReturn(Optional.of(existing));
        when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

        User updated = useCase.execute(new UpdateUserCommand(userId.value().toString(), "Alice2"));

        assertEquals("Alice2", updated.getNickname());
        verify(userRepository).save(existing);
    }

    @Test
    void rejectsMalformedUserIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new UpdateUserCommand("not-a-uuid", "x")));

        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void rejectsUnknownUserId() {
        UserId userId = UserId.from(UUID.randomUUID());
        when(userRepository.findById(userId)).thenReturn(Optional.empty());

        assertThrows(UserNotFoundException.class,
                () -> useCase.execute(new UpdateUserCommand(userId.value().toString(), "x")));

        verify(userRepository, never()).save(any(User.class));
    }
}
