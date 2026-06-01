package cc.agentcook.application.port.in;

import cc.agentcook.domain.session.SessionId;

/**
 * Input Port: open a new conversation session for an existing user.
 */
public interface CreateSessionUseCase {

    SessionId execute(CreateSessionCommand command);
}
