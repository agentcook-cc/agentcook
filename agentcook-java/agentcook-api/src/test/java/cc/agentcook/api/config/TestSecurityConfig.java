package cc.agentcook.api.config;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Test-profile {@link SecurityFilterChain} that permits everything.
 * Replaces the production OAuth2 Resource Server chain when
 * {@code @ActiveProfiles("test")} is active — keeps the existing
 * Controller integration tests passing without rewriting each one
 * to attach a Bearer token.
 *
 * <p>Authentication wiring is exercised separately by
 * {@code SecurityIntegrationTest} (no {@code test} profile, real
 * production chain) which proves valid/missing/invalid JWT paths.</p>
 */
@TestConfiguration
@Profile("test")
public class TestSecurityConfig {

    @Bean
    @Primary
    public SecurityFilterChain testSecurityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .httpBasic(basic -> basic.disable())
                .formLogin(form -> form.disable())
                .logout(logout -> logout.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
        return http.build();
    }
}
