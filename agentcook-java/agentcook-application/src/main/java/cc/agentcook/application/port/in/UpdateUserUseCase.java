package cc.agentcook.application.port.in;

import cc.agentcook.domain.user.User;

/**
 * Input Port: update an existing user's profile (nickname only —
 * status transitions are separate use cases).
 */
public interface UpdateUserUseCase {

    User execute(UpdateUserCommand command);
}
