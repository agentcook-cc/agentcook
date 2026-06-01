package cc.agentcook.api.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import io.swagger.v3.oas.models.servers.Server;
import org.springdoc.core.models.GroupedOpenApi;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;
import java.util.Map;

@Configuration
public class OpenApiConfig {

    private static final String BEARER_AUTH = "bearerAuth";

    @Bean
    public OpenAPI agentcookJavaOpenApi() {
        Info info = new Info()
                .title("agentcook Java Business API")
                .version("1.0.0")
                .description("""
                        Java business backend (ADR-013): User / Session / Plugin / Connector / Permission.
                        Memory / Soul / Identity APIs live in the Python runtime and are documented in
                        docs/api/v1.yaml (maintained by Agent A).

                        ## Authentication
                        All `/api/v1/**` endpoints (except `/api/v1/auth/login`) require a `Bearer` JWT
                        in the `Authorization` header. Obtain one by POSTing username/password to
                        `/api/v1/auth/login`; the token is an HS256-signed JWT with a 1h TTL.

                        ## Versioning
                        URL-versioned (`/api/v1/...`). Breaking changes open a new `/api/v2/...` namespace
                        with a 6-month deprecation window — see docs/api/DEPRECATION-POLICY.md.
                        """)
                .contact(new Contact().name("agentcook").url("https://agentcook.cc"))
                .license(new License().name("Apache-2.0").url("https://www.apache.org/licenses/LICENSE-2.0"));

        info.setExtensions(Map.of(
                "x-frozen", "2026-05-31",
                "x-scope", "java-business",
                "x-source", "springdoc-openapi (auto-generated from controllers)"
        ));

        Components components = new Components()
                .addSecuritySchemes(BEARER_AUTH, new SecurityScheme()
                        .type(SecurityScheme.Type.HTTP)
                        .scheme("bearer")
                        .bearerFormat("JWT")
                        .description("HS256-signed JWT issued by `POST /api/v1/auth/login`."));

        return new OpenAPI()
                .info(info)
                .servers(List.of(
                        new Server().url("http://localhost:8080").description("Local dev"),
                        new Server().url("https://api.agentcook.cc").description("Production")))
                .components(components)
                .addSecurityItem(new SecurityRequirement().addList(BEARER_AUTH));
    }

    /**
     * Default group: every {@code /api/v1/**} endpoint. The Swagger UI
     * dropdown lists this group by name.
     */
    @Bean
    public GroupedOpenApi v1Api() {
        return GroupedOpenApi.builder()
                .group("v1")
                .pathsToMatch("/api/v1/**")
                .build();
    }

    /**
     * Tag-scoped groups make the Swagger UI dropdown searchable by
     * resource — handy when the v1 surface grows past ~30 operations.
     * Group names match the {@code @Tag(name = ...)} on each controller
     * so the documentation site (Agent B) can deep-link by tag.
     */
    @Bean
    public GroupedOpenApi authGroup() {
        return GroupedOpenApi.builder().group("auth").pathsToMatch("/api/v1/auth/**").build();
    }

    @Bean
    public GroupedOpenApi usersGroup() {
        return GroupedOpenApi.builder()
                .group("users")
                .pathsToMatch("/api/v1/users/**", "/api/v1/permissions/**")
                .build();
    }

    @Bean
    public GroupedOpenApi sessionsGroup() {
        return GroupedOpenApi.builder().group("sessions").pathsToMatch("/api/v1/sessions/**").build();
    }

    @Bean
    public GroupedOpenApi pluginsGroup() {
        return GroupedOpenApi.builder().group("plugins").pathsToMatch("/api/v1/plugins/**").build();
    }

    @Bean
    public GroupedOpenApi connectorsGroup() {
        return GroupedOpenApi.builder().group("connectors").pathsToMatch("/api/v1/connectors/**").build();
    }
}
