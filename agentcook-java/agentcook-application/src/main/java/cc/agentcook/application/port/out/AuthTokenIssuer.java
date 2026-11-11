package cc.agentcook.application.port.out;

import cc.agentcook.application.exception.InvalidRefreshTokenException;
import cc.agentcook.application.port.in.AuthTokens;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserId;

/**
 * Output Port: mint and verify the bearer tokens handed to clients.
 *
 * <p>The adapter decides the token format (HS256 JWTs shared with the
 * Python runtime today) and which roles / scopes a user's access token
 * carries; use cases only decide <em>whether</em> a user gets tokens.</p>
 */
public interface AuthTokenIssuer {

    /** Issue a fresh access + refresh token pair for an authenticated user. */
    AuthTokens issue(User user);

    /**
     * Verify a refresh token (signature, issuer, expiry, token type) and
     * return the user it was issued to. Does not check that the user
     * still exists or is active — that is the caller's job.
     *
     * @throws InvalidRefreshTokenException for any token that is not a
     *         valid, unexpired refresh token from this issuer
     */
    UserId verifyRefreshToken(String refreshToken);
}
