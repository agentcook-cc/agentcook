package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.CreateSessionCommand;
import cc.agentcook.application.port.in.CreateSessionUseCase;
import cc.agentcook.domain.session.Session;
import cc.agentcook.domain.session.SessionId;
import cc.agentcook.domain.session.SessionRepository;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class CreateSessionUseCaseImpl implements CreateSessionUseCase {

    private final UserRepository userRepository;
    private final SessionRepository sessionRepository;

    public CreateSessionUseCaseImpl(UserRepository userRepository,
                                    SessionRepository sessionRepository) {
        this.userRepository = userRepository;
        this.sessionRepository = sessionRepository;
    }

    @Override
    public SessionId execute(CreateSessionCommand command) {
        UserId userId = UserId.from(command.userId());
        userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException(userId));
        Session session = Session.create(userId, command.title());
        return sessionRepository.save(session).getId();
    }
}
