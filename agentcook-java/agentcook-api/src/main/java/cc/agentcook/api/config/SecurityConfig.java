package cc.agentcook.api.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;

import javax.crypto.spec.SecretKeySpec;

/**
 * Phase 3 Day 31: OAuth2 Resource Server + JWT verification (HS256 dev
 * secret today, JWKS swap Phase 4). Replaces the Day 24
 * {@code WebSecurityCustomizer.ignoring("/**")} dev-mode bypass.
 *
 * <p>Public endpoints (no token required):
 * <ul>
 *   <li>{@code POST /api/v1/auth/login} — issues the JWT</li>
 *   <li>{@code /v3/api-docs/**} + {@code /swagger-ui/**} — spec docs</li>
 *   <li>{@code /actuator/health} + {@code /actuator/prometheus} — ops probes</li>
 * </ul>
 *
 * <p>Everything else requires a {@code Bearer} token signed with the
 * dev secret from {@code agentcook.auth.jwt-secret} (override via env
 * {@code AGENTCOOK_AUTH_JWT_SECRET}; minimum 32 bytes).</p>
 *
 * <p>Phase 4 Day 33-34 swaps {@code NimbusJwtDecoder.withSecretKey} for
 * {@code .withJwkSetUri} once a real identity issuer is in place.</p>
 */
@Configuration
public class SecurityConfig {

    private final String jwtSecret;

    public SecurityConfig(@Value("${agentcook.auth.jwt-secret}") String jwtSecret) {
        if (jwtSecret == null || jwtSecret.getBytes().length < 32) {
            throw new IllegalStateException(
                    "agentcook.auth.jwt-secret must be at least 32 bytes (HS256). " +
                            "Set AGENTCOOK_AUTH_JWT_SECRET in prod.");
        }
        this.jwtSecret = jwtSecret;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .httpBasic(basic -> basic.disable())
                .formLogin(form -> form.disable())
                .logout(logout -> logout.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
                                "/api/v1/auth/login",
                                "/v3/api-docs", "/v3/api-docs/**",
                                "/swagger-ui.html", "/swagger-ui/**",
                                "/actuator/health", "/actuator/health/**",
                                "/actuator/info",
                                "/actuator/prometheus"
                        ).permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()));
        return http.build();
    }

    @Bean
    public JwtDecoder jwtDecoder() {
        SecretKeySpec key = new SecretKeySpec(jwtSecret.getBytes(), "HmacSHA256");
        return NimbusJwtDecoder.withSecretKey(key).build();
    }
}
