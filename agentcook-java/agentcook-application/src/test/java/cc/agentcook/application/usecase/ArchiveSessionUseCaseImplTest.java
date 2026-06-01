package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.SessionNotFoundException;
import cc.agentcook.application.port.in.ArchiveSessionCommand;
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
class ArchiveSessionUseCaseImplTest {

    @Mock private SessionRepository sessionRepository;
    @InjectMocks private ArchiveSessionUseCaseImpl useCase;

    @Test
    void archivesActiveSession() {
        SessionId sessionId = SessionId.generate();
        Session session = Session.reconstitute(sessionId, UserId.generate(), "S",
                SessionStatus.ACTIVE, Instant.now(), Instant.now());
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.of(session));
        when(sessionRepository.save(any(Session.class))).thenAnswer(inv -> inv.getArgument(0));

        Session archived = useCase.execute(new ArchiveSessionCommand(sessionId.value().toString()));

        assertEquals(SessionStatus.ARCHIVED, archived.getStatus());
        verify(sessionRepository).save(session);
    }

    @Test
    void rejectsUnknownSessionId() {
        SessionId sessionId = SessionId.from(UUID.randomUUID());
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.empty());

        assertThrows(SessionNotFoundException.class,
                () -> useCase.execute(new ArchiveSessionCommand(sessionId.value().toString())));

        verify(sessionRepository, never()).save(any(Session.class));
    }

    @Test
    void rejectsArchivingDeletedSessionPerDomainInvariant() {
        SessionId sessionId = SessionId.generate();
        Session deleted = Session.reconstitute(sessionId, UserId.generate(), "S",
                SessionStatus.DELETED, Instant.now(), Instant.now());
        when(sessionRepository.findById(sessionId)).thenReturn(Optional.of(deleted));

        assertThrows(IllegalStateException.class,
                () -> useCase.execute(new ArchiveSessionCommand(sessionId.value().toString())));

        verify(sessionRepository, never()).save(any(Session.class));
    }
}
