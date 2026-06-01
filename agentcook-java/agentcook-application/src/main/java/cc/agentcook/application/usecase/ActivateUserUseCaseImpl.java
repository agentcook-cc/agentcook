package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.UserNotFoundException;
import cc.agentcook.application.port.in.ActivateUserCommand;
import cc.agentcook.application.port.in.ActivateUserUseCase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class ActivateUserUseCaseImpl implements ActivateUserUseCase {

    private final UserRepository userRepository;

    public ActivateUserUseCaseImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public User execute(ActivateUserCommand command) {
        UserId userId = UserId.from(command.userId());
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException(userId));
        user.activate();
        return userRepository.save(user);
    }
}
