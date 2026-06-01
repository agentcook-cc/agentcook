package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.SuspendUserCommand;
import cc.agentcook.application.port.in.SuspendUserUseCase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class SuspendUserUseCaseImpl implements SuspendUserUseCase {

    private final UserRepository userRepository;

    public SuspendUserUseCaseImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public User execute(SuspendUserCommand command) {
        UserId userId = UserId.from(command.userId());
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException(userId));
        user.suspend();
        return userRepository.save(user);
    }
}
