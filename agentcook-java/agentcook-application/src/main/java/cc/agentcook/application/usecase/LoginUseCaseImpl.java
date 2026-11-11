package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.AccountDisabledException;
import cc.agentcook.application.exception.InvalidCredentialsException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.in.LoginCommand;
import cc.agentcook.application.port.in.LoginUseCase;
import cc.agentcook.application.port.out.AuthTokenIssuer;
import cc.agentcook.application.port.out.PasswordHasher;
import cc.agentcook.domain.user.LoginIdentity;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.util.UUID;

/**
 * Password login.
 *
 * <ul>
 *   <li><b>Known user with a password</b> — the password must match;
 *       then the account must be ACTIVE (credentials are checked first so
 *       the "disabled" answer is only given to someone who knows the
 *       password).</li>
 *   <li><b>Known user without a password</b> (seed data, rows from the
 *       old any-password dev login, admin-created users) — rejected,
 *       unless {@code agentcook.auth.auto-provision} is on, in which case
 *       the first login claims the account by setting its password.</li>
 *   <li><b>Unknown user</b> — rejected, unless auto-provision is on, in
 *       which case the account is created with this password.</li>
 * </ul>
 *
 * <p>Auto-provision is a development convenience (on in the {@code dev}
 * profile only). Rejected logins still spend one hash comparison so
 * response time does not reveal whether an identity exists.</p>
 */
@Service
@Transactional
public class LoginUseCaseImpl implements LoginUseCase {

    private final UserRepository userRepository;
    private final PasswordHasher passwordHasher;
    private final AuthTokenIssuer tokenIssuer;
    private final boolean autoProvision;

    /** Hash of a random value, compared against on rejected logins (timing equaliser). */
    private volatile String decoyHash;

    public LoginUseCaseImpl(UserRepository userRepository,
                            PasswordHasher passwordHasher,
                            AuthTokenIssuer tokenIssuer,
                            @Value("${agentcook.auth.auto-provision:false}") boolean autoProvision) {
        this.userRepository = userRepository;
        this.passwordHasher = passwordHasher;
        this.tokenIssuer = tokenIssuer;
        this.autoProvision = autoProvision;
    }

    @Override
    public AuthTokens execute(LoginCommand command) {
        LoginIdentity identity;
        try {
            identity = LoginIdentity.parse(command.username());
        } catch (IllegalArgumentException malformed) {
            throw reject(command.password());
        }

        Optional<User> found = userRepository.findByEmail(identity.email());
        if (found.isEmpty()) {
            if (!autoProvision) {
                throw reject(command.password());
            }
            return tokenIssuer.issue(provision(identity, command.password()));
        }

        User user = found.get();
        if (user.hasPassword()) {
            if (!passwordHasher.matches(command.password(), user.getPasswordHash())) {
                throw new InvalidCredentialsException();
            }
            requireActive(user);
            return tokenIssuer.issue(user);
        }

        if (!autoProvision) {
            throw reject(command.password());
        }
        requireActive(user);
        return tokenIssuer.issue(claim(user.getId(), command.password()));
    }

    private User provision(LoginIdentity identity, String password) {
        User user = User.create(identity.email(), identity.username());
        user.changePasswordHash(passwordHasher.hash(password));
        return userRepository.save(user);
    }

    /** First login on a password-less row sets its password (under the row lock). */
    private User claim(UserId userId, String password) {
        User locked = userRepository.findByIdForUpdate(userId)
                .orElseThrow(InvalidCredentialsException::new);
        if (locked.hasPassword()) {
            // Claimed concurrently between our read and the lock: verify instead.
            if (!passwordHasher.matches(password, locked.getPasswordHash())) {
                throw new InvalidCredentialsException();
            }
            return locked;
        }
        locked.changePasswordHash(passwordHasher.hash(password));
        return userRepository.save(locked);
    }

    private static void requireActive(User user) {
        if (!user.isActive()) {
            throw new AccountDisabledException(user.getStatus());
        }
    }

    private InvalidCredentialsException reject(String password) {
        passwordHasher.matches(password, decoyHash());
        return new InvalidCredentialsException();
    }

    private String decoyHash() {
        String hash = decoyHash;
        if (hash == null) {
            hash = passwordHasher.hash(UUID.randomUUID().toString());
            decoyHash = hash;
        }
        return hash;
    }
}
