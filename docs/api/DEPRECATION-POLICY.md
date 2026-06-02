# API Deprecation Policy

This policy applies to **all `/api/v1/**` endpoints in `java-v1.yaml` and
`v1.yaml`** — the agentcook public REST surface. Internal endpoints
(`/actuator/**`, `/v3/api-docs`) are exempt.

## Versioning model

URL-path versioning: the major version sits in the path (`/api/v1/`,
`/api/v2/`, …). We picked this over header-based versioning because:

- It's visible in access logs and dashboards without parsing
- Caching infrastructure (CDN, reverse proxy) treats different versions
  as distinct resources naturally
- Frontend codegen tools (`openapi-typescript`) emit cleaner
  per-version type files

**Minor and patch versions are tracked in `info.version`** in the OpenAPI
spec (`1.0.0` → `1.1.0` → `1.2.0` for the Python runtime; `1.0.0` only
for Java to date — additive changes don't bump version, only `v2.yaml`
does). The `info.x-frozen` field stamps the freeze date.

## What counts as breaking

| Change | Breaking? | Action |
|---|:---:|---|
| Add a new endpoint | ❌ | additive — append to current major |
| Add an optional request field | ❌ | additive |
| Add a new response field | ❌ | clients ignore unknown fields |
| Remove a response field | ✅ | new major or 6-month deprecation |
| Rename a field | ✅ | new major (a remove + add is breaking) |
| Make an optional field required | ✅ | new major |
| Tighten validation (regex, length, enum) | ✅ | new major |
| Change HTTP status code semantics | ✅ | new major |
| Add a new required header (e.g. new auth scheme) | ✅ | new major |
| Add a new optional query param | ❌ | additive |
| Remove an endpoint | ✅ | 6-month deprecation, then new major |

When in doubt, assume breaking. The cost of a false negative (a silent
client break in production) is much higher than the cost of a false
positive (a deprecation cycle for a change that would have been safe).

## Deprecation timeline

When an endpoint or field is marked deprecated:

| Phase | Duration | What we do |
|---|:---:|---|
| **T0 — Mark deprecated** | day 0 | Add `@Deprecated` annotation in code, set `Deprecation` + `Sunset` response headers, announce in `CHANGELOG.md`, file follow-up tickets for known consumers |
| **T0 + 1 month** | 30 days | Email each known consumer team; broadcast on the project Slack / community board |
| **T0 + 3 months** | 90 days | Reminder broadcast; if telemetry shows >5% of traffic still on the deprecated path, escalate to the owning team |
| **T0 + 5 months** | 150 days | Final notice; switch logs from `INFO` to `WARN` on every deprecated-endpoint hit |
| **T0 + 6 months** | 180 days | **Sunset.** Endpoint removed in the next release; or, if it's a field, response stops including it |

The 6-month minimum is non-negotiable for `/api/v1` surface. Internal
consumers (admin BFF talking to itself) can negotiate faster sunset on
a case-by-case basis, but external consumers always get 6 months.

## Response headers

Every deprecated response carries:

```
Deprecation: true
Sunset: Sun, 06 Dec 2026 00:00:00 GMT
Link: <https://agentcook.cc/docs/api/migration-v1-to-v2>; rel="deprecation"
```

- `Deprecation: true` — RFC 9745. Clients that understand the header
  can log/alert.
- `Sunset: <HTTP-date>` — RFC 8594. The date the endpoint stops
  responding.
- `Link: ... rel="deprecation"` — points at a migration guide
  (Markdown in the docs site).

In Java, add the headers via a small `OncePerRequestFilter` triggered by
the `@Deprecated` annotation on the handler method:

```java
@Deprecated(since = "1.2.0", forRemoval = true)
@PostMapping("/legacy-endpoint")
public ResponseEntity<...> legacyEndpoint() { ... }
```

The filter inspects `HandlerMethod` and stamps the headers for any
deprecated mapping. This keeps the policy declarative (one annotation
per method) instead of scattered `response.addHeader(...)` calls.

## `@Deprecated` annotation use

In Java code:

```java
/**
 * @deprecated since 1.2.0 — use {@link #newEndpoint()} instead.
 *     Sunset: 2026-12-06. See docs/api/migration-v1-to-v2.md.
 */
@Deprecated(since = "1.2.0", forRemoval = true)
```

- `since` matches the spec version that marked it deprecated
- `forRemoval = true` triggers IDE warnings for any internal caller
- Javadoc `@deprecated` mirrors `since` and links to the replacement

In OpenAPI spec, springdoc emits `deprecated: true` on the operation
automatically when the controller method has `@Deprecated`.

## CHANGELOG entries

Every deprecation lands in `docs/api/CHANGELOG.md` under the version
that introduced the deprecation, in a `### Deprecations` subsection:

```markdown
### Deprecations (sunset 2026-12-06)

- `POST /api/v1/legacy-endpoint` → replaced by `POST /api/v1/new-endpoint`.
  Migration guide: docs/api/migration-v1-to-v2.md
```

## What to do at sunset

When the 6-month timer is up:

1. Confirm telemetry shows <0.1% traffic on the deprecated path (else
   negotiate extension — don't break good actors)
2. Remove the handler method (don't leave it returning 410 — that's
   what the sunset means)
3. Remove the deprecation entry from `CHANGELOG.md` (it's now in the
   `v2.yaml` "what changed" section)
4. Bump the spec major version: `v1.yaml` → `v2.yaml`
5. The old `v1.yaml` stays in repo as a frozen artifact for archeology

---

## Minor bump vs major bump — decision tree

When you've made a change and the question is "do I need to cut a new
major or can I just bump minor?", run this tree top-down. Stop at the
first `yes`.

```
┌──────────────────────────────────────────────────────────────────┐
│  Does any existing client that worked against v1.N break against │
│  this server, with zero code change on the client?               │
└────────────────┬─────────────────────────┬───────────────────────┘
                 │ yes                     │ no
                 ▼                         ▼
       ┌─────────────────┐    ┌─────────────────────────────────────┐
       │  MAJOR bump     │    │  Is the change visible in the spec  │
       │  (cut v2.yaml,  │    │  (paths, schemas, params, headers)? │
       │   6-month       │    └─────────┬───────────────────────┬───┘
       │   deprecation)  │              │ yes                   │ no
       └─────────────────┘              ▼                       ▼
                                 ┌──────────────┐      ┌──────────────────┐
                                 │  MINOR bump  │      │  PATCH bump      │
                                 │  (rewrite    │      │  (prose only —   │
                                 │   v1.yaml,   │      │   descriptions,  │
                                 │   1.X+1.0)   │      │   examples)      │
                                 └──────────────┘      └──────────────────┘
```

### Common edge cases

| Change | Bump | Why |
|---|---|---|
| Add `?include=…` query param with default `false` | MINOR | additive — old clients keep their old behavior |
| Add field `created_by` to `UserResponse` | MINOR | response widening — JSON clients ignore unknown fields |
| Rename `created_by` → `creator_id` in response | **MAJOR** | rename = remove + add; old clients reading `created_by` break |
| Change `email` field validation `length<=128` → `length<=255` | MINOR | loosening = old valid input is still valid |
| Change `email` field validation `length<=255` → `length<=128` | **MAJOR** | tightening = previously valid input now 422 |
| Change `500 Internal Server Error` → `503 Service Unavailable` for upstream timeouts | **MAJOR** | client retry logic typically keys off status code |
| Add example to schema description | PATCH | no shape change |
| Reorder fields in response body | MINOR | JSON object ordering is not significant per RFC 8259, but tools that snapshot bytes (Pact, golden tests) see a diff; document in CHANGELOG |
| Add new error code under existing 4xx status | MINOR | new enum value on `ApiError.code`; old clients fall through generic handling |
| Change response from list-of-objects to paginated object `{data: […], total: N}` | **MAJOR** | client iteration code breaks |

### Specific to dual-spec setup

Because Python and Java specs version independently (ADR-013), the
decision tree runs **per spec**. A change that bumps Python v1 → v2
does not require Java to bump, and vice versa.

But: if a cross-cutting change spans both specs (e.g. shared `ApiError`
schema rename), both specs bump on the same day in lock-step — track it
as one entry under each spec's CHANGELOG section.

---

## v1 → v2 migration path

When the moment comes to actually cut v2 (six months after the first
breaking change is announced), this is the runbook. We've never had to
do it in production — but having the steps written down means we won't
panic when we do.

### Phase 1 — `v2` lives next to `v1` (sunset clock T0 → T+6mo)

```
agentcook-cc/docs/api/
├── v1.yaml              # active, info.version: 1.x.y
├── v2.yaml              # NEW, info.version: 2.0.0, info.x-frozen: T+6mo
└── migration-v1-to-v2.md  # NEW, per-endpoint diff table
```

Server changes:

| Step | Java | Python |
|---|---|---|
| 1 | Add v2 controllers under `cc.agentcook.api.v2` (sibling to existing `controller` pkg) | Add v2 routers under `agentcook/src/agentcook_app/routers/v2/` |
| 2 | Mount under `@RequestMapping("/api/v2")` on each v2 controller | `app.include_router(v2_router, prefix="/api/v2")` |
| 3 | Springdoc auto-generates `/v3/api-docs/v2` group; configure `GroupedOpenApi` so `/v3/api-docs/v1` stays pinned to the v1 controllers | FastAPI: separate `OpenAPI` schema per router group |
| 4 | Both `/api/v1` and `/api/v2` serve traffic simultaneously | Same |
| 5 | `/api/v1` responses keep the deprecation headers from `DEPRECATION-POLICY.md` §"Response headers" | Same |

### Phase 2 — `v1` sunset (T+6mo)

Per the sunset checklist above. Specifically for the v1→v2 cut:

1. Run `scripts/check-v1-traffic.sh` — must show <0.1% traffic on
   `/api/v1/**` over the prior 7 days. If not, extend sunset.
2. Replace `/api/v1/**` controller bodies with `410 Gone` returns
   carrying the migration `Link` header. Keep the routes mapped for
   2 weeks so good actors still get a useful error.
3. After 2 weeks, delete the v1 controller package outright. Update
   the springdoc `GroupedOpenApi` to drop the v1 group.
4. Mark `v1.yaml` with `info.deprecated: true` at the spec root and
   keep the file in repo — it's the canonical archeological record.
5. CHANGELOG entry under v2.0.0 reads `### Removed — see v1 → v2
   migration guide`.

### Phase 3 — `v2` is sole live surface (T+6mo + 2 weeks onwards)

The dual-spec setup makes this cleaner than monolithic versioning: if
only the **Python** spec is doing a v1→v2 cut, the Java `/api/v1/**`
surface is untouched — Java clients don't need to know v2 happened.

### Migration guide template

When v2 first appears (Phase 1, step 0), create
`docs/api/migration-v1-to-v2.md` from this template:

```markdown
# v1 → v2 migration guide

**Sunset date**: <ISO date>
**Breaking changes**: <count>

## Per-endpoint diff

| v1 path | v2 path | What changed | Client action |
|---|---|---|---|
| ... | ... | ... | ... |

## Per-schema diff

| v1 schema | v2 schema | What changed |
|---|---|---|

## SDK release notes

- Python `agentcook-py-client` 1.x → 2.0
- JS/TS `@agentcook/openapi-typescript` 1.x → 2.0
- Java `agentcook-java-client` (Gradle) 1.x → 2.0
```

The guide goes live in `docs-site` under
`https://agentcook.cc/docs/api/migration-v1-to-v2` — that URL is the
target of every deprecated response's `Link: …; rel="deprecation"`
header, so it MUST exist before the first deprecation is announced.

---

## Cross-references

- `docs/api/VERSIONING-POLICY.md` — when/how to bump (this is the
  prequel to the present doc; deprecation is the sequel to a version
  cut)
- `docs/api/CHANGELOG.md` — record of every frozen version
- `docs/adr/ADR-006-blue-green-deployment.md` — deployment slot
  mapping during a v1→v2 cutover
- `docs/adr/ADR-013-java-business-backend.md` — why two specs evolve
  independently
