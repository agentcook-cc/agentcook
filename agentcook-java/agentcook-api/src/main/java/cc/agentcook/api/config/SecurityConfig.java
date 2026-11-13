package cc.agentcook.api.config;

import cc.agentcook.api.auth.JwtTokenIssuer;
import jakarta.servlet.DispatcherType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2ErrorCodes;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtIssuerValidator;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.oauth2.server.resource.authentication.JwtGrantedAuthoritiesConverter;
import org.springframework.security.oauth2.server.resource.web.BearerTokenResolver;
import org.springframework.security.oauth2.server.resource.web.DefaultBearerTokenResolver;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.security.web.util.matcher.RequestMatcher;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;

/**
 * OAuth2 Resource Server: HS256 JWTs signed by {@link JwtTokenIssuer}
 * with the shared secret {@code agentcook.auth.jwt-secret} (env
 * {@code AGENTCOOK_AUTH_JWT_SECRET}; minimum 32 bytes).
 *
 * <p><b>Token checks</b> (on top of the signature): {@code iss} must be
 * {@value JwtTokenIssuer#ISSUER}, {@code exp}/{@code nbf} must be valid,
 * {@code exp} and {@code sub} must be present, and refresh tokens
 * ({@code typ: "refresh"}) are rejected — they are only good for
 * {@code POST /api/v1/auth/refresh}.</p>
 *
 * <p><b>Authorities:</b> the {@code roles} claim maps to {@code ROLE_*}
 * ({@code admin → ROLE_ADMIN}) and {@code scope} to {@code SCOPE_*}.</p>
 *
 * <p><b>Access rules</b> — the whole role policy lives here; data-level
 * ownership (a user may only see their own sessions) is enforced in the
 * controllers, which answer 404 for other users' resources:</p>
 * <ul>
 *   <li>public: {@code POST /api/v1/auth/{login,register,refresh}}, API
 *       docs, health / info / prometheus probes, and error dispatches;</li>
 *   <li>any authenticated user: {@code GET /api/v1/users/me},
 *       {@code /api/v1/quota/**}, {@code /api/v1/sessions/**} (owner
 *       checked), {@code GET /api/v1/plugins};</li>
 *   <li>{@code ROLE_ADMIN}: the rest of {@code /api/v1/users/**}
 *       (user management and permissions), {@code /api/v1/permissions/**},
 *       plugin mutations and everything under {@code /api/v1/connectors}
 *       (connectors are system-wide, not user-owned; incl. ping and the
 *       OAuth callback the admin console posts to);</li>
 *   <li>anything else: authenticated.</li>
 * </ul>
 *
 * <p>401 / 403 answers carry an {@link cc.agentcook.api.dto.ApiError}
 * body (see {@link ApiErrorSecurityHandler}).</p>
 */
@Configuration
public class SecurityConfig {

    private static final String ADMIN = "ADMIN";

    /**
     * The public auth endpoints. A bearer header sent to them is ignored
     * rather than verified, so a client holding an expired access token
     * can still log in or refresh.
     */
    private static final RequestMatcher AUTH_ENDPOINTS = new AntPathRequestMatcher("/api/v1/auth/**");

    private final String jwtSecret;
    private final ApiErrorSecurityHandler errorHandler;

    public SecurityConfig(@Value("${agentcook.auth.jwt-secret}") String jwtSecret,
                          ApiErrorSecurityHandler errorHandler) {
        this.jwtSecret = jwtSecret;
        this.errorHandler = errorHandler;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .httpBasic(basic -> basic.disable())
                .formLogin(form -> form.disable())
                .logout(logout -> logout.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .exceptionHandling(e -> e
                        .authenticationEntryPoint(errorHandler)
                        .accessDeniedHandler(errorHandler))
                .authorizeHttpRequests(auth -> auth
                        // Error dispatches (e.g. a 405 or 415 rendered by Spring
                        // Boot's /error) keep their real status instead of
                        // turning into a 401 for public endpoints.
                        .dispatcherTypeMatchers(DispatcherType.ERROR).permitAll()
                        .requestMatchers(HttpMethod.POST,
                                "/api/v1/auth/login",
                                "/api/v1/auth/register",
                                "/api/v1/auth/refresh"
                        ).permitAll()
                        .requestMatchers(
                                "/v3/api-docs", "/v3/api-docs.yaml", "/v3/api-docs/**",
                                "/swagger-ui.html", "/swagger-ui/**",
                                "/actuator/health", "/actuator/health/**",
                                "/actuator/info",
                                "/actuator/prometheus"
                        ).permitAll()
                        // Users: everyone may read themselves; the rest
                        // (incl. /users/{id}/permissions) is user management.
                        .requestMatchers(HttpMethod.GET, "/api/v1/users/me").authenticated()
                        .requestMatchers("/api/v1/users", "/api/v1/users/**").hasRole(ADMIN)
                        .requestMatchers("/api/v1/permissions", "/api/v1/permissions/**").hasRole(ADMIN)
                        .requestMatchers("/api/v1/connectors", "/api/v1/connectors/**").hasRole(ADMIN)
                        // Plugins: the catalogue is readable by everyone, changes are admin-only.
                        .requestMatchers(HttpMethod.GET, "/api/v1/plugins", "/api/v1/plugins/**").authenticated()
                        .requestMatchers("/api/v1/plugins", "/api/v1/plugins/**").hasRole(ADMIN)
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2
                        .bearerTokenResolver(bearerTokenResolver())
                        .authenticationEntryPoint(errorHandler)
                        .accessDeniedHandler(errorHandler)
                        .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthenticationConverter())));
        return http.build();
    }

    @Bean
    public JwtDecoder jwtDecoder() {
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withSecretKey(JwtTokenIssuer.signingKey(jwtSecret))
                .macAlgorithm(MacAlgorithm.HS256)
                .build();
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
                new JwtTimestampValidator(),
                new JwtIssuerValidator(JwtTokenIssuer.ISSUER),
                new AccessTokenValidator()));
        return decoder;
    }

    /** {@code Authorization: Bearer} header, except on the public auth endpoints. */
    static BearerTokenResolver bearerTokenResolver() {
        DefaultBearerTokenResolver header = new DefaultBearerTokenResolver();
        return request -> AUTH_ENDPOINTS.matches(request) ? null : header.resolve(request);
    }

    /**
     * Authorities = {@code SCOPE_<scope>} for each entry of {@code scope}
     * plus {@code ROLE_<ROLE>} (upper-cased) for each entry of {@code roles},
     * so {@code hasRole("ADMIN")} matches {@code roles: ["user","admin"]}.
     */
    static JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtGrantedAuthoritiesConverter scopes = new JwtGrantedAuthoritiesConverter();
        Converter<Jwt, Collection<GrantedAuthority>> authorities = jwt -> {
            List<GrantedAuthority> granted = new ArrayList<>(scopes.convert(jwt));
            List<String> roles = jwt.getClaimAsStringList(JwtTokenIssuer.CLAIM_ROLES);
            if (roles != null) {
                for (String role : roles) {
                    if (role != null && !role.isBlank()) {
                        granted.add(new SimpleGrantedAuthority("ROLE_" + role.trim().toUpperCase(Locale.ROOT)));
                    }
                }
            }
            return granted;
        };
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(authorities);
        return converter;
    }

    /**
     * Accepts only access tokens: {@code exp} and {@code sub} present and
     * {@code typ} (or {@code token_type}, which the Python runtime also
     * checks) not {@code "refresh"}. Tokens predating the {@code typ} claim
     * are treated as access tokens.
     */
    static final class AccessTokenValidator implements OAuth2TokenValidator<Jwt> {

        @Override
        public OAuth2TokenValidatorResult validate(Jwt jwt) {
            if (jwt.getExpiresAt() == null) {
                return failure("The token has no expiry");
            }
            if (jwt.getSubject() == null || jwt.getSubject().isBlank()) {
                return failure("The token has no subject");
            }
            if (JwtTokenIssuer.TYPE_REFRESH.equals(jwt.getClaimAsString(JwtTokenIssuer.CLAIM_TYPE))
                    || JwtTokenIssuer.TYPE_REFRESH.equals(jwt.getClaimAsString("token_type"))) {
                return failure("Refresh tokens cannot be used to call the API");
            }
            return OAuth2TokenValidatorResult.success();
        }

        private static OAuth2TokenValidatorResult failure(String description) {
            return OAuth2TokenValidatorResult.failure(
                    new OAuth2Error(OAuth2ErrorCodes.INVALID_TOKEN, description, null));
        }
    }
}
