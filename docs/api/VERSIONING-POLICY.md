# API Versioning Policy

This policy governs how the agentcook public REST surface declares,
bumps, and freezes versions. It sits next to `DEPRECATION-POLICY.md`
(which covers what to do **after** a version is marked deprecated) and
`CHANGELOG.md` (which records every frozen spec).

Internal endpoints (`/actuator/**`, `/v3/api-docs`, `/metrics`,
`/prometheus`) are out of scope — they evolve with the deployment, not
with the public contract.

---

## Two specs, on purpose

The repo ships **two OpenAPI specs**, not one:

| Spec | Owner | Source of truth | Scope |
|---|---|---|---|
| `docs/api/v1.yaml` | Agent A (Python runtime) | `FastAPI.openapi()` → `scripts/dump-openapi.py` | Memory / Soul / Identity / Skills / Delegations / Logs / Chat |
| `docs/api/java-v1.yaml` | Agent D (Java business) | springdoc-openapi `/v3/api-docs.yaml` | Users / Sessions / Plugins / Connectors / Permissions / OAuth callback / Auth |

The split mirrors **ADR-013** (dual-backend split): Python owns the
agent runtime + memory plane; Java owns auth + business state plane.

**Each spec versions independently.** A Python-only change does not
invalidate Java consumer types and vice versa. Each spec has its own
`info.version` (semver) and its own `info.x-frozen` date stamp.

### Why not merge them?

We considered a single unified spec early in Phase 2. Three reasons we
keep them separate:

1. **Independent release cadence** — the Python runtime ships new
   memory features without touching Java; merging them would require
   coordinating bumps even for orthogonal work.
2. **Smaller blast radius for codegen** — `openapi-typescript` runs
   twice (Python types + Java types) but produces two smaller modules,
   so a Java field rename doesn't churn Python consumer imports.
3. **Clear ownership** — when a field changes, the spec file's `Owner`
   column above answers "who's accountable" in one line.

---

## Versioning scheme

We use **semver** (`MAJOR.MINOR.PATCH`) on the OpenAPI `info.version`,
combined with **URL-path versioning** on the major component.

### Major in the URL path

The major version sits in the path (`/api/v1/`, `/api/v2/`, …). Same
rationale as DEPRECATION-POLICY:

- Visible in access logs and dashboards without parsing
- Caches treat different versions as distinct resources naturally
- Frontend codegen emits cleaner per-version type files

### Minor / patch in `info.version`

The full semver lives in `info.version` inside each YAML:

```yaml
info:
  title: agentcook Python runtime API
  version: 1.2.0
  x-frozen: '2026-06-07'
```

- **MAJOR** bumps when **breaking** changes ship (see DEPRECATION-POLICY
  §"What counts as breaking"). MAJOR bumps cut a new YAML file
  (`v2.yaml`) and live alongside the old one through the 6-month
  deprecation window.
- **MINOR** bumps when **additive** changes ship (new endpoint, new
  optional request field, new response field). The same YAML gets
  rewritten — no `v1.3.yaml` file.
- **PATCH** bumps when only the **prose** changes (descriptions,
  examples, schema name typo) — no shape change. Same YAML.

### `info.x-frozen` is a freeze date

Once `info.x-frozen` is stamped, the YAML is the contract. Downstream
codegen (B's `openapi-typescript`, C's Pact provider verification, D's
springdoc-openapi cross-check) consumes that frozen snapshot. A spec
must never be edited in place after the freeze — bump the version and
add a CHANGELOG entry instead.

---

## What counts as a breaking change

The authoritative table lives in `DEPRECATION-POLICY.md`. Short version:

| Change | MAJOR bump? |
|---|:---:|
| Add a new endpoint | no — MINOR |
| Add an optional request field | no — MINOR |
| Add a new response field | no — MINOR |
| Add a new optional query param | no — MINOR |
| Remove a response field | **yes** |
| Rename a field | **yes** |
| Make optional field required | **yes** |
| Tighten validation (regex / length / enum) | **yes** |
| Change HTTP status code semantics | **yes** |
| Add a new required header / auth scheme | **yes** |
| Remove an endpoint | **yes** (after 6-month deprecation) |

When in doubt, assume MAJOR. A false-negative (silent client break in
prod) costs much more than a false-positive (a deprecation cycle for a
change that would have been safe).

---

## Bump procedure (minor)

When adding an endpoint or optional field:

1. Edit the FastAPI route / Spring controller. **Do not edit the YAML
   by hand** — it gets regenerated from code.
2. Regenerate the spec:
   - Python: `uv run python scripts/dump-openapi.py > docs/api/v1.yaml`
   - Java: `mvn -pl agentcook-api spring-boot:run` then
     `curl http://localhost:8080/v3/api-docs.yaml > docs/api/java-v1.yaml`
3. Bump `info.version` (1.2.0 → 1.3.0) and `info.x-frozen` (today's
   date, ISO 8601).
4. Add a `### v1.3.0 — additive` entry to `docs/api/CHANGELOG.md` with
   the new paths / fields and a `Bumped by` / `Bump type` / `SHA-256`
   header (see existing v1.2.0 entry as template).
5. Run consumer verification:
   - `pnpm --filter @agentcook-cc/app codegen:openapi` (B's
     typescript types regen — must compile)
   - `pytest tests/contract -m contract` (C's Pact provider
     verification — must pass 8/8)
6. Commit with `feat(api): bump v1 1.2.0 → 1.3.0 — <one-line summary>`.

The whole loop is ~10 minutes if no consumer breaks. If consumer
codegen breaks, you've actually made a MAJOR change — go back, mark
the old behavior `@Deprecated`, and bump to MAJOR via the v2
procedure (next section).

## Bump procedure (major)

When introducing a breaking change:

1. Stop. Confirm the change is unavoidable and not a misclassified
   additive change.
2. Mark the old surface `@Deprecated` per `DEPRECATION-POLICY.md` §T0.
   Set `Sunset` 6 months out.
3. Add the new surface in **parallel** under the existing `v1.yaml`.
   Both old and new live in v1 during the deprecation window — no need
   to wait for v2 to start shipping the replacement.
4. When the 6-month sunset arrives:
   - Generate the new `v2.yaml` from the post-removal API (run the
     regenerate step above with version `2.0.0`).
   - Leave `v1.yaml` in repo, marked `info.x-frozen` and
     `info.deprecated: true` at the spec level (Spectral rule
     `spec-deprecated-after-sunset` enforces this in CI).
   - Mount `v2.yaml` at `/api/v2/**`.
   - Old `/api/v1/**` returns `410 Gone` with the migration `Link` for
     2 weeks, then routes are removed.

---

## Client compatibility matrix

Frontend consumers (`agentcook-admin`, `agentcook-app`) and external
SDKs must declare which spec version they target. Compatibility is
forward-tolerant within a major (a client targeting v1.1 keeps working
against v1.2) but **not** backward-tolerant (a client targeting v1.2
will likely break if pointed at v1.1 because it may rely on fields the
server hasn't shipped yet).

| Client | Targets | Compatible servers |
|---|---|---|
| `agentcook-admin` (Vue 3) | v1.2.0 + java-v1.0.0 | v1.2.0–v1.x and java-v1.0.0–v1.x |
| `agentcook-app` (React 19) | v1.2.0 + java-v1.0.0 | v1.2.0–v1.x and java-v1.0.0–v1.x |
| Pact consumer contracts (8 pacts) | v1.2.0 + java-v1.0.0 | matched by C in `pact-broker` |
| External SDK (future) | declared in SDK README | clients declare their version floor |

The matrix lives here, not in each client README, because it's
cross-cutting. Every spec bump must update this table in the same
commit as the YAML bump.

---

## CI enforcement

Three checks gate spec changes:

1. **Spec freshness** — `scripts/check-openapi-fresh.sh` runs the
   regenerate step inside CI and diffs against the committed YAML. A
   non-empty diff fails the build. This catches "I edited the code but
   forgot to regenerate the spec."
2. **Spec lint** — `redocly lint docs/api/v1.yaml` enforces:
   description coverage, no `$ref` cycles, every operation has at
   least one `2xx` response, every error response uses `ApiError`
   schema. Runs in CI on PR.
3. **Pact provider verification** — `pytest tests/contract -m contract`
   replays all 8 consumer pacts against the current Python + Java
   servers. A breaking spec change that slips past the lint will
   surface here, because consumer pacts pin response shapes.

CI failures from any of the three are **not** to be `--no-verify`'d
through. They exist because past spec drift cost us 4 hours of
debugging on Day 27 (consumer types out of sync with server).

---

## Related documents

- `docs/api/DEPRECATION-POLICY.md` — what to do after a version is
  marked deprecated (timeline, response headers, sunset checklist)
- `docs/api/CHANGELOG.md` — every frozen spec version with its
  additions and SHA-256
- `docs/adr/ADR-013-java-business-backend.md` — why two specs, not one
- `docs/adr/ADR-006-blue-green-deployment.md` — how spec versions map
  to deployment slots during major-version rollover
