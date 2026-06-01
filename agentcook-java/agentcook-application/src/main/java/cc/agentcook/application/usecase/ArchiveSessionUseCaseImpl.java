package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.SessionNotFoundException;
import cc.agentcook.application.port.in.ArchiveSessionCommand;
import cc.agentcook.application.port.in.ArchiveSessionUseCase;
import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class ArchiveSessionUseCaseImpl implements ArchiveSessionUseCase {

    private final SessionRepository sessionRepository;

    public ArchiveSessionUseCaseImpl(SessionRepository sessionRepository) {
        this.sessionRepository = sessionRepository;
    }

    @Override
    public Session execute(ArchiveSessionCommand command) {
        SessionId sessionId = SessionId.from(command.sessionId());
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new SessionNotFoundException(sessionId));
        session.archive();
        return sessionRepository.save(session);
    }
}
