package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.InvalidRefreshTokenException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.application.port.in.RefreshTokenCommand;
import cc.agentcook.application.port.in.RefreshTokenUseCase;
import cc.agentcook.application.port.out.AuthTokenIssuer;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;
import cc.agentcook.domain.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Exchange a refresh token for a new access + refresh pair. The user is
 * re-read on every refresh, so suspending an account stops it from
 * obtaining new access tokens (already-issued ones live until they
 * expire — keep the access TTL short).
 */
@Service
@Transactional(readOnly = true)
public class RefreshTokenUseCaseImpl implements RefreshTokenUseCase {

    private final UserRepository userRepository;
    private final AuthTokenIssuer tokenIssuer;

    public RefreshTokenUseCaseImpl(UserRepository userRepository, AuthTokenIssuer tokenIssuer) {
        this.userRepository = userRepository;
        this.tokenIssuer = tokenIssuer;
    }

    @Override
    public AuthTokens execute(RefreshTokenCommand command) {
        UserId userId = tokenIssuer.verifyRefreshToken(command.refreshToken());
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new InvalidRefreshTokenException("user no longer exists"));
        if (!user.isActive()) {
            throw new InvalidRefreshTokenException("account is not active");
        }
        return tokenIssuer.issue(user);
    }
}
