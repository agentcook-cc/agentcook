package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListSessionsQuery;
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
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ListSessionsUseCaseImplTest {

    @Mock private SessionRepository sessionRepository;
    @InjectMocks private ListSessionsUseCaseImpl useCase;

    @Test
    void listsSessionsForUser() {
        UserId userId = UserId.generate();
        Session s1 = Session.reconstitute(SessionId.generate(), userId, "S1",
                SessionStatus.ACTIVE, Instant.now(), Instant.now());
        Session s2 = Session.reconstitute(SessionId.generate(), userId, "S2",
                SessionStatus.ARCHIVED, Instant.now(), Instant.now());
        when(sessionRepository.findByUserId(userId)).thenReturn(List.of(s1, s2));

        List<Session> sessions = useCase.execute(new ListSessionsQuery(userId.value().toString()));

        assertEquals(2, sessions.size());
    }

    @Test
    void returnsEmptyListWhenUserHasNoSessions() {
        UserId userId = UserId.from(UUID.randomUUID());
        when(sessionRepository.findByUserId(userId)).thenReturn(List.of());

        List<Session> sessions = useCase.execute(new ListSessionsQuery(userId.value().toString()));

        assertEquals(0, sessions.size());
    }

    @Test
    void rejectsMalformedUserIdString() {
        assertThrows(IllegalArgumentException.class,
                () -> useCase.execute(new ListSessionsQuery("not-a-uuid")));

        verify(sessionRepository, never()).findByUserId(org.mockito.ArgumentMatchers.any());
    }
}
