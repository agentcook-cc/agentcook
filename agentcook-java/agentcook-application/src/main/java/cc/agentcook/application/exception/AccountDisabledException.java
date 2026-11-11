package cc.agentcook.application.exception;

import cc.agentcook.domain.user.UserStatus;

/**
 * The account exists but is not {@link UserStatus#ACTIVE} (suspended or
 * deleted), so it may not sign in or consume quota.
 */
public class AccountDisabledException extends RuntimeException {

    public AccountDisabledException(UserStatus status) {
        super("Account is " + status.name().toLowerCase(java.util.Locale.ROOT));
    }
}
