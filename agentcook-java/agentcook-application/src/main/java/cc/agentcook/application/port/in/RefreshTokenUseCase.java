package cc.agentcook.application.port.in;

/**
 * Input Port: exchange a refresh token for a fresh access + refresh pair.
 */
public interface RefreshTokenUseCase {

    /**
     * @throws cc.agentcook.application.exception.InvalidRefreshTokenException
     *         when the token is invalid / expired / not a refresh token, or
     *         its user no longer exists or is not active
     */
    AuthTokens execute(RefreshTokenCommand command);
}
