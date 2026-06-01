package cc.agentcook.application.exception;

import cc.agentcook.domain.session.SessionId;

public class SessionNotFoundException extends RuntimeException {

    public SessionNotFoundException(SessionId sessionId) {
        super("Session not found: " + sessionId);
    }
}
