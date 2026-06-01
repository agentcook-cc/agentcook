# OWASP Top 10 — agentcook security checklist

Owner: Agent C. Phase 4 Day 42 — first formal pass against the live
swarm topology (gateway + agent-core + admin-bff + connector + 5
domain aggregates).

> Status legend: ✅ verified PASS · 🟡 partial / mitigated · 🔴 open
> finding · 📅 deferred to Phase 5 Day 51

Each item lists: **what** the threat is on this codebase specifically,
**how** we tested, **result**, and **fix / next step**. "Tested" rows
are reproducible — run the command and you should see the same result.

---

## A01:2021 — Broken Access Control

### Threat surface
- Java `agentcook-java` exposes `/api/v1/users`, `/sessions`, `/plugins`,
  `/connectors`, `/permissions`. Spring Security OAuth2 (Day 31) gates
  every endpoint except the auth-public allow-list.
- Python `agentcook` exposes `/api/v1/agents/*`, `/skills/*`, `/memory/*`
  — JWT verification middleware (`agentcook_app.security`) gates them.

### Tested
```
# 1. No token → 401 envelope
curl -i http://127.0.0.1:8080/api/v1/users
curl -i http://127.0.0.1:8000/api/v1/agents/agt-001/identity

# 2. Tampered token → 401 AUTH_INVALID_TOKEN
curl -i -H "Authorization: Bearer not.a.real.token" \
  http://127.0.0.1:8000/api/v1/agents/agt-001/identity

# 3. Expired token → 401 AUTH_TOKEN_EXPIRED
# Reproduce via tests/test_main.py::test_endpoint_with_expired_token_returns_envelope
```

### Result
✅ All three return 401 with structured `ErrorEnvelope`. Covered by
`agentcook/tests/test_main.py` (3 token-failure paths) and Spring
SecurityFilterChain integration tests.

### Fix / next step
- 📅 Phase 5 Day 51: add an IDOR test — log in as user A, attempt
  `GET /api/v1/users/<userB>`. Today's PermissionController doesn't
  consult the requesting user's identity yet (Day 30 wired up Permission
  CRUD but not user-scoped reads).

---

## A02:2021 — Cryptographic Failures

### Threat surface
- JWT signing: HMAC-SHA256 with `AGENTCOOK_JWT_SECRET` (Day 31
  Spring Security; matching key in Python middleware).
- pgvector / postgres-business: postgres password in env vars
  (`POSTGRES_PASSWORD`).
- TLS in transit: gateway termination by Traefik (Day 38-40).

### Tested
- `grep -RIn "AGENTCOOK_JWT_SECRET\|POSTGRES_PASSWORD" docker-compose.dev.yml`
  → only env references, no secrets baked into images.
- `docker history agentcook/admin-bff:latest` → no plaintext secrets in
  image layers.

### Result
🟡 Dev profile uses placeholder strings (`"dev-only-do-not-use-in-prod"`).
Production-grade KDF / sealed-secret pipeline tracked in `values-prod.yaml`
but not yet exercised — Phase 4 Day 47 release prep depends on it.

### Fix / next step
- 🔴 Open: `values-prod.yaml` references `Secret` resources but the
  `templates/secret.yaml` ships placeholders. Before prod deploy, replace
  with `external-secrets.io` or sealed-secret references.
- 📅 Phase 5 Day 51: enforce `min(secret_length) >= 32` and rotate keys
  via `kubectl rollout restart`.

---

## A03:2021 — Injection

### Threat surface
| Vector | Where | Defended by |
|---|---|---|
| SQL injection | Java `JpaRepository` queries; Python `agentcook-storage` | JPA prepared statements (no raw SQL); psycopg `%s` parameter binding |
| Command injection | None: agentcook does not shell out except inside the plugin sandbox (covered by sandbox-penetration.md) | — |
| OS path traversal | Plugin upload (`POST /api/v1/plugins`) extracts a zip | covered below |

### Tested
```bash
# SQL injection — Java
curl -X POST http://127.0.0.1:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice'\'' OR 1=1 --","password":"x"}'
# → returns 200 (dev profile dummy auth) but query stays parameterised;
#   no syntax error, no extra rows leaked.

# Path traversal — Plugin upload
zip -j /tmp/evil.zip /etc/passwd
curl -X POST http://127.0.0.1:8080/api/v1/plugins \
  -F "file=@/tmp/evil.zip"
# → expect rejection; Java `PluginController.upload` should not
#   write outside the configured plugin directory.
```

### Result
✅ SQL: JPA prepared statements verified by static read of all
`*Repository.java` files — no `@Query` uses string concatenation.
Python: psycopg's `cursor.execute("SELECT ... %s", (val,))` is the only
pattern seen via grep.

🟡 Plugin upload path traversal: the Day 27 PluginController
implementation defers extraction to Phase 5; the unzip path is not yet
hardened. **Tracked as open below.**

### Fix / next step
- 🔴 Open: harden plugin zip extraction — reject any entry whose
  resolved path falls outside the destination directory (classic ZIP
  Slip CVE-2018-1002200). Owner: D, Phase 5 Day 51.
- 📅 Phase 5 Day 51: schemathesis fuzz against frozen v1.2.0 spec
  with malformed payloads.

---

## A04:2021 — Insecure Design

### Threat surface
- Permission model is allow/deny pairs, not RBAC. Day 30 protocol
  decision (coordinator代决) — accept the simplification, document
  upgrade path.

### Result
🟡 Documented design choice. Not a vulnerability; flagged so future
audits don't mistake the absence of Roles for an oversight.

### Fix / next step
- 📅 Phase 5: if customer feedback names "Role" as a UX gap, layer
  Role-as-permission-bundle on top without changing the domain
  aggregate. Tracked in coordinator decisions log Day 30.

---

## A05:2021 — Security Misconfiguration

### Threat surface
- Spring Security: `SecurityConfig` previously `web.ignoring("/**")`
  in dev mode. Day 31 swap to OAuth2 Resource Server.
- CORS: configured both at FastAPI (`CORSMiddleware`) and Traefik
  middleware level — risk of duplicate headers / drift.
- Actuator endpoints: `health/info/metrics` exposed; `prometheus`
  added Day 25 P0.
- Default postgres / redis credentials in dev compose.

### Tested
```bash
# Confirm SecurityConfig is not ignoring all routes
grep -A 2 "web.ignoring" agentcook-java/.../config/SecurityConfig.java
# Confirm CORS doesn't allow `*` in prod
grep -A 5 "allow_origins\|allowedOrigins" agentcook/src/.../main.py \
  agentcook-swarm/gateway/dynamic/middlewares.yml
```

### Result
✅ Day 31 replaced `web.ignoring("/**")` with explicit allowlist
(`/auth/login`, `/v3/api-docs`, `/swagger-ui`, `/actuator/health/**`).
✅ CORS allowlists the admin (5173) + app (5174) dev origins;
production origins read from env (`AGENTCOOK_CORS_ORIGINS`).

🟡 Traefik dynamic config also sets CORS — confirm it doesn't
double-emit `Access-Control-Allow-Origin`. Tested Day 42 morning;
Traefik strips the upstream header before adding its own.

### Fix / next step
- 📅 Phase 5 Day 51: add a SecurityHeader middleware (X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy, Permissions-Policy).
  None present today.

---

## A06:2021 — Vulnerable and Outdated Components

See sibling file `vuln-scan-2026-05-22.md` (this Day 42 run).
Summary:

| Stack | Tool | High | Critical |
|---|---|---:|---:|
| Python (uv) | `pip-audit` | 0 | 0 |
| Frontend | `pnpm audit` | TBD | TBD |
| Java (Maven) | `mvn dependency-check:check` | TBD | TBD |

(Numbers filled by the scan task; treat empty as "scan attempted but
tool not available locally".)

---

## A07:2021 — Identification and Authentication Failures

### Threat surface
- Dev profile: any non-empty creds → `dev-token-{username}`.
- Production: real JWT (HS256, 1h TTL).
- Token refresh: `refresh_token` returned on login (Day 26 Day 31).

### Tested
- 3 token-failure paths in `agentcook/tests/test_main.py` cover missing,
  expired, and malformed bearer tokens.

### Result
✅ Dev profile clearly marked (`AuthController` writes `dev-token-`
prefix). Production swap is gated on env (`SPRING_PROFILES_ACTIVE`).

### Fix / next step
- 🔴 Open: rate-limit `/auth/login` (currently no per-IP throttle).
  Traefik has a `rate-limit` middleware; wire it for prod via
  `agentcook-swarm/gateway/dynamic/middlewares.yml`. Owner: B + C,
  Phase 4 Day 46 prod-readiness.
- 📅 Phase 5: brute-force lockout policy on repeated failed logins.

---

## A08:2021 — Software and Data Integrity Failures

### Threat surface
- `pip install` from PyPI mirrors (Tsinghua) — supply-chain risk.
- npm dependencies (admin / app / design-tokens / docs-site) — same.
- Docker base images: `pgvector/pgvector:pg16`, `redis:7-alpine`,
  `eclipse-temurin:17-jre-jammy`, `quay.io/prometheus/prometheus:v2.53.0`.

### Result
🟡 Lockfiles committed (`uv.lock`, `pnpm-lock.yaml`, Maven pom version
pins). No SBOM yet, no Sigstore / cosign verification.

### Fix / next step
- 📅 Phase 5 Day 51: generate SBOM via `cyclonedx-cli` for Python +
  `cyclonedx-bom-plugin` for Maven. Push to GitHub Releases.

---

## A09:2021 — Security Logging and Monitoring Failures

### Threat surface
- structlog (Python) + slf4j (Java) emit JSON. OTel traces via
  Jaeger. Prometheus metrics for service health.

### Tested
```bash
# Force a 401 and check it's traced + logged
curl -i http://127.0.0.1:8080/api/v1/users
# Then in Jaeger UI: search service=admin-bff status=4xx
```

### Result
✅ 401s land in Jaeger as spans tagged `http.status_code=401`.
🟡 No alerting yet — Prometheus has metrics but no AlertManager rules.

### Fix / next step
- 📅 Phase 4 Day 46: Prometheus alert rules (auth failure spike,
  5xx spike, p99 latency over baseline).

---

## A10:2021 — Server-Side Request Forgery (SSRF)

### Threat surface
- Plugin sandbox can run arbitrary user code (covered in
  `sandbox-penetration.md`).
- `agentcook-providers` makes outbound calls to OpenAI / Anthropic /
  Qwen / etc. — SSRF risk if the provider URL is user-controlled.

### Tested
- `grep -RIn "base_url" agentcook-providers/src` → all base URLs read
  from env or constructor args; no path constructed from user input.

### Result
✅ Provider base URLs are server-side configuration; no user-controlled
path participates.

🟡 Plugin sandbox network egress — covered in companion file.

### Fix / next step
- 📅 Phase 5 Day 51: explicit allowlist for outbound DNS in plugin
  sandbox (currently network is unrestricted; sandbox-penetration.md
  exercises this).

---

## Summary

| Status | Count | Highlights |
|---|---:|---|
| ✅ verified | 5 | A01 access control, A03 SQL injection (param binding), A05 SecurityFilterChain, A07 auth flow, A09 trace coverage |
| 🟡 partial | 4 | A02 prod secrets, A03 zip slip, A05 SecurityHeaders, A08 SBOM |
| 🔴 open | 3 | zip slip, prod secrets, auth rate-limit |
| 📅 deferred | 6 | per item — Phase 5 Day 51 mostly |

Re-run before each release tag (Phase 4 Day 47).
