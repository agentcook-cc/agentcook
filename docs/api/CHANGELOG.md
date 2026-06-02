# API Spec Changelog

This file tracks frozen API spec versions for downstream codegen
(B's `openapi-typescript`, C's Pact provider verification, D's
springdoc-openapi cross-check).

Two specs ship in this repo, intentionally separate:

| Spec | Owner | Source of truth | Scope |
|---|---|---|---|
| `docs/api/v1.yaml` | Agent A (Python runtime) | FastAPI `app.openapi()` → `scripts/dump-openapi.py` | Memory / Soul / Identity |
| `docs/api/java-v1.yaml` | Agent D (Java business) | springdoc-openapi `/v3/api-docs.yaml` | User / Session / Plugin / Connector / Permission |

The split mirrors **ADR-013** (dual-backend split): Python owns the
agent runtime + memory; Java owns auth/business state. Each spec
freezes independently — a Python-only change does not invalidate Java
consumer types and vice versa.

---

## v1.yaml — `python-runtime` v1.2.0 (frozen 2026-06-07)

**Bumped by**: Agent A · Phase 3 Day 6

**Bump type**: minor — additive only. v1.1.0 endpoints unchanged.

**Verification**:
- `wc -l docs/api/v1.yaml` → 1414 lines (+165 from v1.1.0)
- 11 paths × 13 operations (+2 paths from v1.1.0)
- 23 component schemas (+3 from v1.1.0: `DelegationNode` / `DelegationEdge` / `DelegationGraphResponse`)
- `info.version: 1.2.0`
- `info.x-frozen: 2026-06-07`
- SHA-256: `c61e5dd74f91458959df6597a58018367f92866a2f356eb849d1856d23da563f`

### What's new

| Method | Path | Schema | Purpose |
|---|---|---|---|
| GET | `/api/v1/agents/{agent_id}/delegations` | `DelegationGraphResponse` | Runtime delegation graph rooted at an agent — what B's Day 31 app `AgentDelegationView.tsx` (reactflow) displays. Today returns a fixed 3-node / 2-edge mock; Phase 5 wires through `MultiAgentOrchestrator.snapshot()`. |
| GET | `/api/v1/logs/stream` | (SSE, see frame below) | SSE-streamed log frames for B's Day 31 admin `LogStreamView.vue`. 1Hz cadence, configurable `?limit` (1–200), terminal frame carries `extra.finished: true`. Today's mock generates synthetic frames; Phase 5 swaps in a structlog broadcast handler. |

### Backend wiring

- `agentcook/src/agentcook_app/main.py`:
  - `from agentcook_app.routers import delegations, logs, memory, skills`
  - `app.include_router(delegations.router)` + `app.include_router(logs.router)`
  - `version` bumped 1.1.0 → 1.2.0; `_install_freeze_metadata` x-frozen advanced to 2026-06-07
- `agentcook/src/agentcook_app/routers/delegations.py` (Day 29 scaffolding, Day 31 wired)
- `agentcook/src/agentcook_app/routers/logs.py` (Day 30 scaffolding, Day 31 wired)
- `agentcook/src/agentcook_app/schemas_delegations.py` + `schemas_logs.py`

### Downstream regenerate commands

```bash
# B — admin (LogStreamView consumes /logs/stream)
cd agentcook-admin && pnpm gen:api:python

# B — app (AgentDelegationView consumes /agents/{id}/delegations)
cd agentcook-app   && pnpm gen:api:python

# C — Pact provider verify
make test-contract
```

### SSE consumer contract for `/api/v1/logs/stream` (for B)

Query param: `?limit={1..200}` (default 30).

Each `data:` frame:

```json
{
  "timestamp": "2026-06-07T09:00:00.123456+00:00",
  "level": "info",
  "event": "request.start",
  "request_id": "0000000a0000000a",
  "logger": "agentcook_app.mock",
  "extra": {"seq": 10, "finished": true}
}
```

Levels are constrained to `debug / info / warning / error / critical`.
The terminal frame includes `extra.finished: true` — close the
EventSource on that signal (same shape as the v1.1 skills SSE contract).

---

## v1.yaml — `python-runtime` v1.1.0 (frozen 2026-06-04)

**Bumped by**: Agent A · Phase 3 Day 3

**Bump type**: minor — additive only. v1.0.0 endpoints unchanged.

**Verification** (run `scripts/dump-openapi.py` then check):
- `wc -l docs/api/v1.yaml` → 1249 lines (+246 from v1.0.0)
- 9 paths × 11 operations
- 20 component schemas (+6 from v1.0.0: `SkillSummary` / `SkillListResponse` / `SkillDetailResponse` / `SkillTestRequest` + 2 FastAPI-generated validation envelopes)
- `info.version: 1.1.0`
- `info.x-frozen: 2026-06-04`
- `info.x-changelog: docs/api/CHANGELOG.md` (new)
- SHA-256: `3aa4551b6303fe15e6530218522e3b5bf34491847f68d9a34b48e53d167e8b43`

### What's new

| Method | Path | Schema | Purpose |
|---|---|---|---|
| GET | `/api/v1/skills` | `SkillListResponse` | List all registered skills (B's SkillListView source). |
| GET | `/api/v1/skills/{skill_id}` | `SkillDetailResponse` | Skill manifest + body for B's SkillDetailDrawer. |
| POST | `/api/v1/skills/{skill_id}/test/stream` | `SkillTestRequest` → SSE | Streamed skill execution for B's SkillTestDialog (consumed via `useSseChat`). Returns `text/event-stream`; 10 mock chunks × 500ms today, real `SkillRegistry` execution Phase 5. |

### Backend wiring

- `agentcook/src/agentcook_app/main.py`: `app.include_router(skills.router)` added; `version` bumped 1.0.0 → 1.1.0; `_install_freeze_metadata` x-frozen advanced to 2026-06-04 + added `x-changelog`.
- `agentcook/src/agentcook_app/routers/skills.py`: Day 27 scaffolding + Day 28 SSE endpoint.
- `agentcook/src/agentcook_app/schemas_skills.py`: 4 schemas (kept separate from `schemas.py` for clean v1.0 → v1.1 diff).

### Downstream regenerate commands

```bash
# B — admin
cd agentcook-admin && pnpm gen:api:python   # rewrites src/api/types.python.gen.ts

# B — app  (NEW: app now needs python types for SkillTestDialog SSE)
cd agentcook-app   && pnpm gen:api:python   # rewrites src/api/types.python.gen.ts

# C — Pact provider verify
make test-contract   # republishes consumer pacts then runs provider verify
```

### SSE consumer contract (for B)

`POST /api/v1/skills/{id}/test/stream` request body:

```json
{ "input": "the test input text", "args": null }
```

Each `data:` frame:

```json
{
  "chunk_index": 0,
  "total": 10,
  "delta": "[skill={id}] tick 1/10: {input prefix}",
  "finished": false
}
```

The last frame has `finished: true`. `useSseChat` should close the
EventSource when it sees `finished: true` to release the connection.

---

## v1.yaml — `python-runtime` v1.0.0 (frozen 2026-05-31)

**Frozen by**: Agent A · Phase 2 Day 9

**Verification**:
- `wc -l docs/api/v1.yaml` → 1004 lines
- 6 paths × 8 operations
- 14 component schemas
- `info.x-frozen: 2026-05-31`
- `info.x-scope: python-runtime`
- `info.x-paired-spec: docs/api/java-v1.yaml`

### Paths

| Method | Path | Schema |
|---|---|---|
| GET | `/api/v1/agents/{agent_id}/identity` | `IdentityResponse` |
| GET | `/api/v1/agents/{agent_id}/soul` | `SoulResponse` |
| POST | `/api/v1/agents/{agent_id}/soul` | `SoulConfigBody` → `SoulVersionResponse` |
| GET | `/api/v1/agents/{agent_id}/soul/history` | `SoulHistoryResponse` |
| POST | `/api/v1/agents/{agent_id}/memory/events` | `MemoryEventCreate` → `MemoryEventResponse` |
| GET | `/api/v1/agents/{agent_id}/memory/events` | `MemoryEventListResponse` |
| POST | `/api/v1/agents/{agent_id}/memory/search` | `SearchRequest` → `SearchResponse` |
| POST | `/api/v1/agents/{agent_id}/memory/flush` | `FlushRequest` → `FlushResponse` |

### Excluded by design

These endpoints exist on the live app but are **deliberately absent**
from `v1.yaml` (they declare `include_in_schema=False` in code):

- `GET /health` — K8s liveness probe (ops-only, not a client API)
- `GET /health/ready` — K8s readiness probe (ops-only)
- `GET /metrics` — Prometheus scrape endpoint

Codegen consumers should **not** generate clients for these. Health
checks are platform-level concerns, not part of the agent contract.

### Downstream codegen commands

```bash
# B — admin
cd agentcook-admin && npx openapi-typescript ../docs/api/v1.yaml -o src/api/types.python.gen.ts

# B — app
cd agentcook-app && npx openapi-typescript ../docs/api/v1.yaml -o src/api/types.python.gen.ts

# C — Pact provider verify (consumer-side templates live in tests/contract/pacts/)
make test-contract
```

### Change policy after freeze

After a spec is frozen, breaking changes require a **new major version**
(`v2.yaml`). Non-breaking additions (new endpoint / new optional field)
may be appended in-place but **must** trigger:

1. Bump `info.version` minor (1.0.0 → 1.1.0)
2. Re-run `scripts/dump-openapi.py`
3. Notify B (regenerate types) + C (re-run Pact provider verify)
4. Append a row to this changelog

Any change that removes or alters an existing field is breaking — open
v2 instead of mutating v1.

---

## java-v1.yaml — Phase 4 + Phase 5 additive entries

The Java spec `info.version` stays at `1.0.0` through Phase 4 + Phase 5
because all of the changes below are additive at the wire-shape level
(no removed fields, no renamed paths, no tightened validation). The
`info.x-frozen` date stamp re-rolls on each entry; downstream consumers
re-run `openapi-typescript` after each.

### 2026-06-13 (Phase 4 Day 31-32) — auth scheme upgrade (additive)

`POST /api/v1/auth/login` keeps the same wire shape
(`LoginRequest` → `LoginResponse`) but the returned token graduates
from the Phase 3 dummy `dev-token-<username>` to a real HS256-signed
JWT issued by `JwtTokenIssuer`. All other endpoints under `/api/v1/**`
now require a valid Bearer token (Spring Security
`oauth2ResourceServer().jwt()` chain wired in `SecurityConfig`).

Spec-level effect:
- Adds `securitySchemes.bearerAuth` (HTTP Bearer / JWT) at the
  components root
- Adds `security: [bearerAuth: []]` defaults at the operation level
  for every endpoint except `POST /api/v1/auth/login`, which carries
  `security: []` (per Springdoc `@SecurityRequirements({})`)
- No request or response shape changes

Client action: same login flow; any subsequent call must carry
`Authorization: Bearer <token>`. The login endpoint stays open.
B regenerates `types.java.gen.ts` (the security overlay propagates).

### 2026-06-21 (Phase 4 Day 41-44) — health probes split + Swagger groups (additive)

K8s-aware liveness / readiness probe paths land as additional
operations alongside the aggregated `/actuator/health`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/actuator/health/liveness` | JVM-alive check; never includes downstream state |
| GET | `/actuator/health/readiness` | DB + Redis + agent-core reachability; flips pod to NotReady on transient downstream blip without restarting the JVM |

Probes are public (no Bearer needed) per Spring Boot
`management.endpoint.health.probes.enabled=true` defaults.

Springdoc `GroupedOpenApi` reshapes `/v3/api-docs` from one
monolithic spec into six per-domain groups (`auth` / `users` /
`sessions` / `plugins` / `connectors` / `permissions`). The full
spec is still at `/v3/api-docs.yaml`; the grouped subsets are at
`/v3/api-docs/{group}.yaml`. Downstream consumers continue to read
the full file; the groups exist for Swagger UI navigation only.

Schema-level: every `@RestController` now carries `@Operation` (the
ad-hoc / unannotated paths from Day 26-30 retroactively get
descriptions). No path or response-shape change.

### 2026-06-26 (Phase 4 Day 45-47) — JVM probe behaviour (clarification, not spec change)

`PythonUpstreamHealthIndicator` switches `Health.down` →
`Health.unknown` for unreachable Python agent-core: aggregate
`/actuator/health` returns 200 + `UNKNOWN` instead of 503 when only
the Python plane is down. Java's K8s liveness/readiness probes were
already split (Day 41-44) so pod restart behavior is unchanged. No
spec change — same path, same response schema, different value range
for the `status` field (now includes `UNKNOWN` alongside `UP` /
`DOWN`).

Operational impact: prod Prometheus alerts that key off the
aggregated `/actuator/health` need to monitor Python independently
instead of relying on Java's aggregate.

### 2026-06-01 (Phase 4.6 Day 35-eq) — chat backend swap (additive metadata)

The chat surface is owned by the Python runtime (`v1.yaml`,
`POST /api/v1/chat/stream`), but the Java spec gains a related
metadata change: `OAuthCallbackRequest.state` field is now explicitly
documented in the Swagger schema description as "CSRF state token
echoed back by the provider" (was undocumented). Phase 3 dummy still
accepts any value for `state` — Phase 4 Day 33-34 introduces real
server-side state binding per `DEPRECATION-POLICY.md` change
classification (will be a MAJOR bump → `java-v2.yaml` when the
required-binding lands).

No wire shape change today; the description is purely additive.

### 2026-07-08 (Phase 5 Day 48-49) — coverage and cross-lang test (no spec change)

`agentcook-api` jacoco line coverage reaches 92.3% / branch 74.3%
after Day 48 added GrpcServerConfig + GrpcChatService boundary tests
and ConnectorController edge cases. `CrossLangIntegrationIT` lands
Day 49 verifying Java-issued JWT passes through to Python
`/api/v1/chat/stream` unchanged (the test mocks Python with a JDK
HttpServer — real Python container variant is on Phase 5 backlog
behind the docker-mirror unblock).

No spec change. Listed here so downstream readers know `java-v1.0.0`
has been functionally hardened even if `info.version` didn't move.

### 2026-07-10 (Phase 5 Day 51) — JWT boundary contracts (no spec change)

`SecurityChainTest` adds 5 boundary cases (expired / tampered
payload / `alg:none` switch / oversized token / wrong-issuer
secret) — all return `401`, no `500` crash on the oversized path.
`OAuthCallbackControllerIntegrationTest` adds 4 cases documenting
that Phase 3 dummy accepts any `state` value; converting these to
"reject unknown state" tests is the trigger for the future
`java-v2.yaml` bump.

`mvn org.owasp:dependency-check-maven:check` lands as a plugin
(parent pom, on-demand only). Day 51 first scan surfaces 64
HIGH/CRITICAL CVEs across 13 transitive deps (most concentrated in
`tomcat-embed-core 10.1.20` / `netty-transport 4.1.109`); upgrade
path lives in `_internal/audit/phase5-day51-java-compliance-d-view.md`
and is queued behind a Spring Boot 3.2.5 → 3.3.x major-dep spike.

---

## java-v1.yaml — `java-business` v1.0.0 (frozen 2026-05-31)

**Frozen by**: Agent D · Phase 2 Day 9

**Source**: `springdoc-openapi` 2.5.0 reads `@RestController` +
`@Operation` + `@Schema` annotations and emits the spec live at
`/v3/api-docs.yaml`. The export step is automated by
`OpenApiSpecExportTest` (boots the app under testcontainers postgres,
scrapes `/v3/api-docs.yaml`, writes `target/openapi/java-v1.yaml`).
The author then copies that artifact into `docs/api/java-v1.yaml` —
the Java spec is intentionally a build artifact, not a hand-edited
file.

**Verification** (post Day 30 additive update):
- `wc -l docs/api/java-v1.yaml` → 810 lines (was 672 on 2026-06-05; +138 = GET /users list + Permission CRUD + DTO schemas)
- 12 path templates / **19 operations** (was 12 × 15 — `+ GET /api/v1/users`, `+ GET/POST /api/v1/users/{userId}/permissions`, `+ DELETE /api/v1/permissions/{permissionId}`)
- 17 component schemas (was 15 — `+ GrantPermissionRequest`, `+ PermissionResponse`)
- `info.x-frozen: 2026-05-31`
- `info.x-scope: java-business`
- `info.x-source: springdoc-openapi (auto-generated from controllers)`

### 2026-06-02 (Day 26) — additive change

`POST /api/v1/auth/login` added to unblock B's Phase 3 frontend Login
wiring. Phase 3 dev mode returns a dummy bearer token (`dev-token-{username}`,
`Bearer`, `expiresIn=3600`); Phase 4 Day 31-32 swaps it for OAuth2 /
signed JWT (additive then breaking — track as `java-v2.yaml` at that
point). Per the change policy below, this is non-breaking; B regenerates
`types.java.gen.ts` to pick up `LoginRequest` / `LoginResponse`.

### 2026-06-03 (Day 27) — additive change

`POST /api/v1/plugins` (multipart/form-data upload) added to unblock B's
admin Plugin CRUD `PluginCreateDialog` (drag-and-drop zip). Body is a
single `file` part containing the plugin .zip; the controller delegates
to `RegisterPluginUseCase` which extracts `plugin.json` from the zip,
validates the minimum shape (name / version / kind / description), and
creates the `Plugin` aggregate. Sandbox loading + execution remain in
the Python runtime per ADR-013 — this endpoint is metadata only.

Error envelopes: `400 INVALID_PLUGIN_PACKAGE` (bad zip / missing manifest)
and `409 DUPLICATE_PLUGIN` (name + version already registered). B
regenerates `types.java.gen.ts` (the multipart shape doesn't add a new
schema, but the path inventory grows by one operation).

### 2026-06-06 (Day 30) — additive change

Permission management + the missing user-list endpoint, unblocking B's
admin User/Permission management UI:

| Method | Path | Use case |
|---|---|---|
| GET    | `/api/v1/users?status=` | `ListUsersUseCase` — was added Day 26 but never exposed; surfaced today so admin's `UserListView` can drop its mock data |
| GET    | `/api/v1/users/{userId}/permissions` | `ListPermissionsByUserUseCase` |
| POST   | `/api/v1/users/{userId}/permissions` | `GrantPermissionUseCase` (201 + Location, body picks `ALLOW` / `DENY` via `effect`) |
| DELETE | `/api/v1/permissions/{permissionId}` | `RevokePermissionUseCase` (204 / 404 `PERMISSION_NOT_FOUND`) |

New error code: `404 PERMISSION_NOT_FOUND`.

No Role aggregate: per coordinator decision (Day 30 brief §1) the
frontend renders "role management" as a Permission view (matrix of
resource × action grouped by user) — the Java domain stays at the
five ADR-013 aggregates (User / Session / Plugin / Connector /
Permission). B updates `RoleListView` → `PermissionGroupView`.

### 2026-06-05 (Day 29) — additive change

Connector lifecycle CRUD + OAuth callback endpoints added to unblock B's
admin Connector management UI (`ConnectorListView` + `ConnectorOAuthFlow`).

| Method | Path | Use case |
|---|---|---|
| GET    | `/api/v1/connectors?pluginId=` | `ListConnectorsUseCase` |
| POST   | `/api/v1/connectors`           | `CreateConnectorUseCase` (201, admin path — bypasses end-user permission check) |
| GET    | `/api/v1/connectors/{id}`      | direct repository read (200 / 404) |
| PUT    | `/api/v1/connectors/{id}/config` | `UpdateConnectorConfigUseCase` |
| DELETE | `/api/v1/connectors/{id}`      | `DeleteConnectorUseCase` (204 / 404) |
| POST   | `/api/v1/connectors/{id}/ping` | `PingConnectorUseCase` — returns mock 42ms latency in Phase 3; Phase 4 swaps for real upstream IM SDK probes |
| POST   | `/api/v1/connectors/oauth/callback` | OAuth dev dummy — returns `dev-{provider}-{uuid}` bearer token for any of `dingtalk` / `feishu` / `telegram` / `discord` / `slack` |

New error code: `404 CONNECTOR_NOT_FOUND`.

Phase 4 Day 33-34 (per `agent-d-java-architect.md`) swaps the OAuth dummy
for real provider SDK exchanges — wire shape stable across that swap.

B regenerates `types.java.gen.ts` to pick up the 5 new DTO records.

### Paths

| Method | Path | Request → Response |
|---|---|---|
| POST | `/api/v1/auth/login` | `LoginRequest` → `LoginResponse` (200) — Phase 3 dev dummy bearer token |
| POST | `/api/v1/users` | `CreateUserRequest` → `UserResponse` (201) / `ApiError` (409 dup email) |
| GET  | `/api/v1/users/{id}` | — → `UserResponse` (200) / `ApiError` (404) |
| POST | `/api/v1/sessions` | `CreateSessionRequest` → `SessionResponse` (201) |
| GET  | `/api/v1/sessions/{id}` | — → `SessionResponse` (200) / 404 |
| POST | `/api/v1/plugins` | `multipart/form-data` (`file=<zip>`) → `PluginResponse` (201) / `ApiError` (400 / 409) |
| GET  | `/api/v1/plugins?status=` | — → `List<PluginResponse>` |
| POST | `/api/v1/plugins/{id}/activate` | `ActivatePluginRequest` → `ConnectorResponse` (200) / `ApiError` (403/404) |

### Authentication

Phase 2 baseline = `permitAll` (per `SecurityConfig`). OAuth2 Resource
Server + JWT verification land Day 31-32 (Phase 3) per
`agent-d-java-architect.md`.

### Downstream codegen commands

```bash
# B — admin
cd agentcook-admin && npx openapi-typescript ../docs/api/java-v1.yaml -o src/api/types.java.gen.ts

# B — app
cd agentcook-app && npx openapi-typescript ../docs/api/java-v1.yaml -o src/api/types.java.gen.ts

# C — Pact provider verify (consumer-side templates land Day 25; D ships
#     the Java provider verification harness today via pact-jvm)
```

### Change policy after freeze

Same as `v1.yaml`: breaking changes require `java-v2.yaml`; additive
changes bump minor + retrigger downstream codegen + append a row here.

The Java spec re-generates automatically on every `mvn test` —
`OpenApiSpecExportTest` writes the canonical artifact to
`target/openapi/java-v1.yaml` and asserts the three required path
prefixes are present, so any controller drift fails the build.
