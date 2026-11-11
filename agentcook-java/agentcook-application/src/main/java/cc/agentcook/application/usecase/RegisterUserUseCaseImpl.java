package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.InvalidRegistrationException;
import cc.agentcook.application.exception.UserAlreadyExistsException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.in.RegisterUserCommand;
import cc.agentcook.application.port.in.RegisterUserUseCase;
import cc.agentcook.application.port.out.AuthTokenIssuer;
import cc.agentcook.application.port.out.PasswordHasher;
import cc.agentcook.domain.user.LoginIdentity;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Self-service sign-up: normalise the identity, enforce the password
 * policy, store only the hash, and sign the new user straight in.
 *
 * <p>A concurrent registration of the same identity that slips past the
 * {@code existsByEmail} check is stopped by the {@code uk_users_email}
 * constraint at commit (surfaced as HTTP 409 by the API layer).</p>
 */
@Service
@Transactional
public class RegisterUserUseCaseImpl implements RegisterUserUseCase {

    private final UserRepository userRepository;
    private final PasswordHasher passwordHasher;
    private final AuthTokenIssuer tokenIssuer;

    public RegisterUserUseCaseImpl(UserRepository userRepository,
                                   PasswordHasher passwordHasher,
                                   AuthTokenIssuer tokenIssuer) {
        this.userRepository = userRepository;
        this.passwordHasher = passwordHasher;
        this.tokenIssuer = tokenIssuer;
    }

    @Override
    public AuthTokens execute(RegisterUserCommand command) {
        LoginIdentity identity;
        try {
            identity = LoginIdentity.parse(command.username());
        } catch (IllegalArgumentException invalid) {
            throw new InvalidRegistrationException("username", invalid.getMessage());
        }
        String password = command.password();
        if (password.length() < MIN_PASSWORD_LENGTH || password.length() > MAX_PASSWORD_LENGTH) {
            throw new InvalidRegistrationException("password", "must be between " + MIN_PASSWORD_LENGTH
                    + " and " + MAX_PASSWORD_LENGTH + " characters");
        }
        if (userRepository.existsByEmail(identity.email())) {
            throw new UserAlreadyExistsException(identity.username());
        }
        String nickname = (command.nickname() == null || command.nickname().isBlank())
                ? identity.username()
                : command.nickname().trim();
        User user = User.create(identity.email(), nickname);
        user.changePasswordHash(passwordHasher.hash(password));
        return tokenIssuer.issue(userRepository.save(user));
    }
}
