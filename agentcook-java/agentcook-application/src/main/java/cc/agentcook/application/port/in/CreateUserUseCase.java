package cc.agentcook.application.port.in;

import cc.agentcook.domain.user.UserId;

/**
 * Input Port: register a new user.
 */
public interface CreateUserUseCase {

    UserId execute(CreateUserCommand command);
}
