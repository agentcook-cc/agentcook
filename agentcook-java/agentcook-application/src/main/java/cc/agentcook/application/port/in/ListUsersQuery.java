package cc.agentcook.application.port.in;

import cc.agentcook.domain.user.UserStatus;

/**
 * Input Port query: list users, optionally filtered by status.
 * {@code status} may be {@code null} to mean "any status".
 */
public record ListUsersQuery(UserStatus status) {
}
