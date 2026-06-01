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
