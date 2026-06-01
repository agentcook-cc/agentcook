package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.SessionNotFoundException;
import cc.agentcook.application.port.in.UpdateSessionCommand;
import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import cc.agentcook.domain.session.SessionStatus;
import cc.agentcook.domain.user.UserId;
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
class UpdateSessionUseCaseImplTest {

    @Mock private SessionRepository sessionRepository;
    @InjectMocks private UpdateSessionUseCaseImpl useCase;

    @Test
    void updatesTitleOfExistingSession() {
        SessionId sessionId = SessionId.generate();
        Session session = Session.reconstitute(sessionId, UserId.generate(), "old",
                SessionStatus.ACTIVE, Instant.now(), Instant.now());
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.of(session));
        when(sessionRepository.save(any(Session.class))).thenAnswer(inv -> inv.getArgument(0));

        Session updated = useCase.execute(new UpdateSessionCommand(sessionId.value().toString(), "new"));

        assertEquals("new", updated.getTitle());
        verify(sessionRepository).save(session);
    }

    @Test
    void rejectsMalformedSessionIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new UpdateSessionCommand("not-a-uuid", "x")));

        verify(sessionRepository, never()).save(any(Session.class));
    }

    @Test
    void rejectsUnknownSessionId() {
        SessionId sessionId = SessionId.from(UUID.randomUUID());
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.empty());

        assertThrows(SessionNotFoundException.class,
                () -> useCase.execute(new UpdateSessionCommand(sessionId.value().toString(), "x")));

        verify(sessionRepository, never()).save(any(Session.class));
    }
}
