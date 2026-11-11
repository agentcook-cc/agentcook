package cc.agentcook.api.dto;

import cc.agentcook.application.port.in.AuthTokens;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Token envelope returned by login, register and refresh.")
public record LoginResponse(

        @Schema(description = "HS256 JWT for the `Authorization: Bearer` header "
                + "(claims: sub, iss, iat, exp, typ=access, roles, scope, preferred_username).")
        String accessToken,

        @Schema(example = "Bearer", defaultValue = "Bearer")
        String tokenType,

        @Schema(example = "3600", description = "Seconds until the access token is no longer accepted.")
        long expiresIn,

        @Schema(description = "HS256 JWT (typ=refresh) accepted only by `POST /api/v1/auth/refresh`.")
        String refreshToken,

        @Schema(example = "2592000", description = "Seconds until the refresh token is no longer accepted.")
        long refreshExpiresIn
) {

    public static LoginResponse from(AuthTokens tokens) {
        return new LoginResponse(tokens.accessToken(), "Bearer", tokens.accessExpiresInSeconds(),
                tokens.refreshToken(), tokens.refreshExpiresInSeconds());
    }

    @Override
    public String toString() {
        return "LoginResponse[tokenType=" + tokenType + ", expiresIn=" + expiresIn
                + ", refreshExpiresIn=" + refreshExpiresIn + "]";
    }
}
