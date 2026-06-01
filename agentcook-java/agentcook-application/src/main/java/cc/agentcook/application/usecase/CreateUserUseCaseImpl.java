package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.DuplicateEmailException;
import cc.agentcook.application.port.in.CreateUserCommand;
import cc.agentcook.application.port.in.CreateUserUseCase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class CreateUserUseCaseImpl implements CreateUserUseCase {

    private final UserRepository userRepository;

    public CreateUserUseCaseImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public UserId execute(CreateUserCommand command) {
        if (userRepository.existsByEmail(command.email())) {
            throw new DuplicateEmailException(command.email());
        }
        User user = User.create(command.email(), command.nickname());
        return userRepository.save(user).getId();
    }
}
