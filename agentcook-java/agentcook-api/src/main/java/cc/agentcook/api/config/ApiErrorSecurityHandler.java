package cc.agentcook.api.config;

import cc.agentcook.api.dto.ApiError;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.server.resource.web.BearerTokenAuthenticationEntryPoint;
import org.springframework.security.oauth2.server.resource.web.access.BearerTokenAccessDeniedHandler;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Gives the 401 / 403 answers produced by the security filter chain the
 * same {@link ApiError} JSON body as every controller error. Status and
 * the RFC 6750 {@code WWW-Authenticate} header come from Spring's bearer
 * token handlers; this class only adds the body.
 *
 * <ul>
 *   <li>401 {@code AUTH_MISSING_TOKEN} — no {@code Authorization: Bearer} header;</li>
 *   <li>401 {@code AUTH_INVALID_TOKEN} — bad signature / issuer, expired,
 *       or a refresh token used as an access token;</li>
 *   <li>403 {@code AUTH_FORBIDDEN} — valid token without the admin role
 *       on an admin endpoint.</li>
 * </ul>
 *
 * <p>The codes match the Python runtime's, so a client handles both
 * services' auth failures the same way.</p>
 */
@Component
public class ApiErrorSecurityHandler implements AuthenticationEntryPoint, AccessDeniedHandler {

    private final BearerTokenAuthenticationEntryPoint bearerEntryPoint = new BearerTokenAuthenticationEntryPoint();
    private final BearerTokenAccessDeniedHandler bearerAccessDenied = new BearerTokenAccessDeniedHandler();
    private final ObjectMapper objectMapper;

    public ApiErrorSecurityHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
                         AuthenticationException authException) throws IOException {
        bearerEntryPoint.commence(request, response, authException);
        ApiError error = authException instanceof OAuth2AuthenticationException
                ? new ApiError("AUTH_INVALID_TOKEN", authException.getMessage())
                : new ApiError("AUTH_MISSING_TOKEN", "Missing Bearer token.");
        write(response, error);
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                       AccessDeniedException accessDeniedException) throws IOException {
        bearerAccessDenied.handle(request, response, accessDeniedException);
        write(response, new ApiError("AUTH_FORBIDDEN", "This operation requires the admin role."));
    }

    private void write(HttpServletResponse response, ApiError error) throws IOException {
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        objectMapper.writeValue(response.getOutputStream(), error);
    }
}
