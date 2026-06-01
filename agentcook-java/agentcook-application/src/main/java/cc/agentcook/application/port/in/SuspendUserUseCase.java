package cc.agentcook.application.port.in;

import cc.agentcook.domain.user.User;

/**
 * Input Port: suspend an active user. Domain enforces that deleted
 * users may not be suspended.
 */
public interface SuspendUserUseCase {

    User execute(SuspendUserCommand command);
}
