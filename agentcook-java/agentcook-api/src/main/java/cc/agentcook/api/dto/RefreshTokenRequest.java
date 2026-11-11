package cc.agentcook.api.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

@Schema(description = "Refresh-token exchange payload.")
public record RefreshTokenRequest(

        @Schema(description = "The `refreshToken` from a previous login / register / refresh response. "
                + "`refresh_token` is accepted as an alias.")
        @JsonAlias("refresh_token")
        @NotBlank
        String refreshToken
) {

    @Override
    public String toString() {
        return "RefreshTokenRequest[refreshToken=<redacted>]";
    }
}
