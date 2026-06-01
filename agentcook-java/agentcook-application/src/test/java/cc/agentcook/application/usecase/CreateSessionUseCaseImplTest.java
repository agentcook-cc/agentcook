package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.CreateSessionCommand;
import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CreateSessionUseCaseImplTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private SessionRepository sessionRepository;

    @InjectMocks
    private CreateSessionUseCaseImpl useCase;

    @Test
    void createsSessionForExistingUser() {
        UserId userId = UserId.generate();
        User existing = User.reconstitute(
                userId, "alice@example.com", "Alice",
                cc.agentcook.domain.user.UserStatus.ACTIVE,
                java.time.Instant.now(), java.time.Instant.now());
        when(userRepository.findById(userId)).thenReturn(Optional.of(existing));
        when(sessionRepository.save(any(Session.class))).thenAnswer(inv -> inv.getArgument(0));

        SessionId sessionId = useCase.execute(
                new CreateSessionCommand(userId.value().toString(), "Hello"));

        assertNotNull(sessionId);
        verify(sessionRepository).save(any(Session.class));
    }

    @Test
    void rejectsMalformedUserIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new CreateSessionCommand("not-a-uuid", "Hello")));

        verify(sessionRepository, never()).save(any(Session.class));
    }

    @Test
    void rejectsUnknownUserId() {
        UserId userId = UserId.from(UUID.randomUUID());
        when(userRepository.findById(userId)).thenReturn(Optional.empty());

        assertThrows(UserNotFoundException.class,
                () -> useCase.execute(new CreateSessionCommand(userId.value().toString(), "Hello")));

        verify(sessionRepository, never()).save(any(Session.class));
    }
}
