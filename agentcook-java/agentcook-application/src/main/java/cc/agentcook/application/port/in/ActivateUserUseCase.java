package cc.agentcook.application.port.in;

import cc.agentcook.domain.user.User;

/**
 * Input Port: re-activate a suspended user. Domain enforces that
 * deleted users may not be activated.
 */
public interface ActivateUserUseCase {

    User execute(ActivateUserCommand command);
}
