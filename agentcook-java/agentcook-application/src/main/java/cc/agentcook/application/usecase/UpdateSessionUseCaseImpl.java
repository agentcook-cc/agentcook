package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.SessionNotFoundException;
import cc.agentcook.application.port.in.UpdateSessionCommand;
import cc.agentcook.application.port.in.UpdateSessionUseCase;
import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class UpdateSessionUseCaseImpl implements UpdateSessionUseCase {

    private final SessionRepository sessionRepository;

    public UpdateSessionUseCaseImpl(SessionRepository sessionRepository) {
        this.sessionRepository = sessionRepository;
    }

    @Override
    public Session execute(UpdateSessionCommand command) {
        SessionId sessionId = SessionId.from(command.sessionId());
        Session session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new SessionNotFoundException(sessionId));
        session.updateTitle(command.title());
        return sessionRepository.save(session);
    }
}
