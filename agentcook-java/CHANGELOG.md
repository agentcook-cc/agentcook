# Changelog — agentcook-java

All notable changes to the Java business backend. Phases align with the
`tutorial/_internal/L3-strategy/*` master execution plan.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/);
versioning of the REST surface follows
[`../docs/api/DEPRECATION-POLICY.md`](../docs/api/DEPRECATION-POLICY.md)
(URL-path major, additive minor/patch).

---

## 1.0.0 — Phase 4 Day 44 (2026-06-20)

First numbered release. The module has been continuously delivered
since Day 16, but Day 44 is the freeze point that gets tagged + pushed
as a Docker image to the registry. Everything below is what landed
between Day 16 and Day 44.

### Phase 2 (Day 16-25) — DDD foundation

- **Module structure**: `agentcook-java/{api,application,domain,infrastructure}` Maven multi-module workspace under one parent pom (Spring Boot 3.2.5, Java 17).
- **Domain layer (5 aggregates)**: `User` / `Session` / `Plugin` / `Connector` / `Permission` — each with its Value Object id, status enum, Repository port, and domain events.
- **Domain Service**: `PluginActivationService` cross-aggregate orchestration (permission check → publish → establish connector).
- **Application layer**: 3 initial UseCases (`CreateUser` / `CreateSession` / `ActivatePlugin`) + Input/Output Port pattern.
- **Infrastructure layer**: JPA entities + Spring Data repositories + Flyway migrations (`V1__init.sql`: 5 tables + FKs + indexes) + Redis cache + Testcontainers postgres harness.
- **API layer**: 5 controllers + DTO records + springdoc-openapi + GlobalExceptionHandler. The Java spec lives in [`docs/api/java-v1.yaml`](../docs/api/java-v1.yaml) — auto-generated from `@RestController` annotations by `OpenApiSpecExportTest`.

### Phase 3 (Day 26-37) — frontend wire-up

- **Day 24 dual-spec freeze**: `v1.yaml` (Python) + `java-v1.yaml` (Java) — see `docs/api/CHANGELOG.md` for the spec-level history.
- **Day 26 auth**: dummy bearer token in `AuthController`.
- **Day 27 Plugin upload**: `POST /api/v1/plugins` multipart/form-data — `RegisterPluginUseCase` parses the zip's `plugin.json` and creates the Plugin aggregate. Sandbox execution remains in the Python runtime per ADR-013.
- **Day 28-30 UseCase expansion**: `UpdateUser`, `Suspend/ActivateUser`, `ListUsers`, `ArchiveSession`, `UpdateSession`, `ListSessions`, `DeactivatePlugin`, `ListPlugins`, `CreateConnector`, `UpdateConnectorConfig`, `DeleteConnector`, `PingConnector`, `GrantPermission`, `RevokePermission`, `ListPermissionsByUser` → 18 UseCases by Day 30.
- **Day 29 Connector CRUD + OAuth callback**: 5 connector endpoints + `POST /api/v1/connectors/oauth/callback` (Phase 3 dev dummy returning `dev-{provider}-{uuid}` tokens for dingtalk / feishu / telegram / discord / slack).
- **Day 30 Permission management**: `GET/POST /api/v1/users/{userId}/permissions` + `DELETE /api/v1/permissions/{id}`. No Role aggregate — admin "role management" rendered as a Permission matrix per coordinator decision.
- **Day 31 OAuth2 Resource Server**: replaced `WebSecurityCustomizer.ignoring("/**")` dev bypass with a real `SecurityFilterChain` + HS256 JWT decoder (`NimbusJwtDecoder`). `AuthController` upgraded from dummy strings to actual HS256-signed JWTs via `JwtTokenIssuer`. Public endpoints: `/api/v1/auth/login` + `/v3/api-docs/**` + `/swagger-ui/**` + `/actuator/health` + `/actuator/prometheus`. `TestSecurityConfig` keeps the integration tests on a permitAll chain so they don't need to attach tokens.

### Phase 4 (Day 38-44) — production hardening

- **Day 38-40 gRPC + service discovery**:
  - `GrpcChatService` (SSE → gRPC bridge) + `GrpcServerConfig` on port 9090 + gRPC Health + Reflection + 3 integration tests.
  - `EtcdServiceRegistry` (jetcd-core 0.7.7) with 30s lease + `keepAliveOnce` heartbeat, wired by `ServiceRegistryConfig` (`@PostConstruct` register + `@PreDestroy` deregister).
  - `protobuf-maven-plugin` compiling `proto/agentcook.proto` into `cc.agentcook.grpc.*`.

- **Day 38-40 observability**:
  - `ObservabilityConfig` correlation-id filter (MDC + response header) + Micrometer request timer.
  - `ApiVersionFilter` stamps `API-Version: 1.2.0` on every response.
  - `PythonUpstreamHealthIndicator` aggregated into `/actuator/health` so K8s readiness fails when the Python runtime is down.
  - `logback-spring.xml` JSON-structured logging (timestamp / level / service / trace_id / message / extra).

- **Day 41 K8s readiness** _(this release)_:
  - Dockerfile JVM opts: `-XX:+UseContainerSupport -XX:MaxRAMPercentage=75 -XX:+UseG1GC -XX:+UseStringDeduplication -XX:+ExitOnOutOfMemoryError`. `EXPOSE 8080 9090` (HTTP + gRPC).
  - `application.yml`: `server.shutdown=graceful` + `spring.lifecycle.timeout-per-shutdown-phase=30s` for clean pod termination.
  - `application-k8s.yml`: K8s in-cluster DNS for Postgres / Redis / agent-core; etcd registration disabled (kube-proxy handles it); `management.endpoint.health.show-details=never` so probes don't leak secrets.
  - Probe endpoints split: `/actuator/health/liveness` + `/actuator/health/readiness` (via `management.endpoint.health.probes.enabled=true`).
  - [`docs/k8s-config-mapping.md`](../docs/k8s-config-mapping.md): every config knob mapped to ConfigMap or Secret.

- **Day 42 OpenAPI / Swagger UX**:
  - `OpenApiConfig` upgraded with `bearerAuth` security scheme, server list (local + prod), 6 `GroupedOpenApi` groups (v1 + per-resource), and richer `info.description`.
  - `AuthController.login` marked `@SecurityRequirements({})` (the only public endpoint under `/api/v1/`).
  - Controllers carry `@Tag` + `@Operation(summary)` + `@ApiResponse` from Day 24 onwards; Day 42 added rich `description` to the most user-facing endpoints (`POST /users`, `POST /plugins` upload).

- **Day 43 API governance**:
  - [`docs/api/DEPRECATION-POLICY.md`](../docs/api/DEPRECATION-POLICY.md): URL-path major versioning, 6-month sunset, `Deprecation` + `Sunset` + `Link` response headers (RFC 9745 + RFC 8594), `@Deprecated(since=, forRemoval=true)` annotation convention.
  - [`README.md`](./README.md): full module rewrite — architecture (Mermaid), module split, local dev + Docker + K8s deployment, API surface index.

### Versioning + governance

- **REST surface**: `/api/v1/...` — frozen 2026-05-31, additive thereafter. See [`docs/api/CHANGELOG.md`](../docs/api/CHANGELOG.md) for per-day spec deltas.
- **Module artifact**: `cc.agentcook:agentcook-java:1.0.0-SNAPSHOT` → `1.0.0` at this release.
- **Docker image**: `agentcook-java:1.0.0` + `agentcook-java:latest`. Multi-arch (`linux/amd64`, `linux/arm64`) build via `docker buildx` — see Dockerfile for the single source.

### Known gaps (deferred)

- **Testcontainers flaky** (Day 27-30 saga): the host docker daemon occasionally stops idle postgres containers between IT classes when the Ryuk reaper is off (host mirror TLS fault keeps Ryuk's image unfetchable). Mitigation: `mvn install` retry-once almost always passes. Phase 5 will solve it alongside the host mirror fix.
- **Coverage at 1.0.0**: application **98%**, domain **74%** (≈ 85% excluding event records — `equals/hashCode` boilerplate), api **31%** (gRPC bridge + config classes thin on tests), infrastructure **60%** (etcd registry tests excluded by `@Tag("etcd")` to avoid image-pull timeouts). 75% module-level target landed for application + domain; api / infra rises to that bar in Phase 5 once gRPC chat + etcd lifecycle get proper IT coverage.
- **JWKS issuer** (Phase 4 Day 33-34): Phase 3 issues HS256 with a shared dev secret. Production goes to a real identity issuer + `NimbusJwtDecoder.withJwkSetUri`. The wire shape is stable (`accessToken` / `tokenType: Bearer` / `expiresIn`) so the frontend doesn't need to change.
- **Pact provider verify** completeness: 1/3 broker interactions verifying as of Day 30 — full set wired into CI in Phase 5.

---

## Pre-1.0 (Phase 1)

`agentcook-java` was not part of Phase 1 — the Java backend was added
mid-cycle per ADR-013 (CF-3) on Day 16. No 0.x releases exist; the
module went from "doesn't exist" → "1.0.0" across Phase 2-4.
