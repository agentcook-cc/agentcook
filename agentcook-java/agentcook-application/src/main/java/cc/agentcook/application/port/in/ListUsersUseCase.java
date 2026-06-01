package cc.agentcook.application.port.in;

import cc.agentcook.domain.user.User;

import java.util.List;

public interface ListUsersUseCase {

    List<User> execute(ListUsersQuery query);
}
