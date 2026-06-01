package cc.agentcook.application.exception;

import cc.agentcook.domain.user.UserId;

public class UserNotFoundException extends RuntimeException {

    public UserNotFoundException(UserId userId) {
        super("User not found: " + userId);
    }
}
