package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.ListUsersQuery;
import cc.agentcook.application.port.in.ListUsersUseCase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ListUsersUseCaseImpl implements ListUsersUseCase {

    private final UserRepository userRepository;

    public ListUsersUseCaseImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public List<User> execute(ListUsersQuery query) {
        if (query.status() == null) {
            return userRepository.findAll();
        }
        return userRepository.findByStatus(query.status());
    }
}
