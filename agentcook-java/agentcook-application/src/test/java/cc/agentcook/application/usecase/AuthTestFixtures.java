package cc.agentcook.application.usecase;

import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.out.PasswordHasher;
import cc.agentcook.domain.user.User;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * Deterministic test doubles for the auth output ports, so use case
 * tests read as behaviour ("the stored hash is hash(pw)") rather than
 * as Mockito wiring.
 */
final class AuthTestFixtures {

    private AuthTestFixtures() {
    }

    /** Reversible fake: {@code hash(pw) = "hashed:" + pw}. Counts calls to matches. */
    static final class FakePasswordHasher implements PasswordHasher {

        final AtomicInteger matchCalls = new AtomicInteger();

        @Override
        public String hash(String rawPassword) {
            return "hashed:" + rawPassword;
        }

        @Override
        public boolean matches(String rawPassword, String passwordHash) {
            matchCalls.incrementAndGet();
            return passwordHash != null && passwordHash.equals(hash(rawPassword));
        }
    }

    /** Token pair whose access token names the user, so tests can assert who got it. */
    static AuthTokens tokensFor(User user) {
        return new AuthTokens("access-" + user.getEmail(), 3600, "refresh-" + user.getEmail(), 2_592_000);
    }
}
