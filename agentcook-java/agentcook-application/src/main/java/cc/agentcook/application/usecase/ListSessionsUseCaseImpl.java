package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListSessionsQuery;
import cc.agentcook.application.port.in.ListSessionsUseCase;
import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionRepository;
import cc.agentcook.domain.user.UserId;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ListSessionsUseCaseImpl implements ListSessionsUseCase {

    private final SessionRepository sessionRepository;

    public ListSessionsUseCaseImpl(SessionRepository sessionRepository) {
        this.sessionRepository = sessionRepository;
    }

    @Override
    public List<Session> execute(ListSessionsQuery query) {
        UserId userId = UserId.from(query.userId());
        return sessionRepository.findByUserId(userId);
    }
}
