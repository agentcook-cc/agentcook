# Frontend API Client

Day 24 onwards we operate two backends in parallel (ADR-008 / ADR-013):

- **Python runtime** (`agentcook` FastAPI, port 8000) — Memory / Soul / Identity / health
- **Java business** (`agentcook-java` Spring Boot, port 8080) — User / Session / Plugin / Connector / Permission

Each backend owns its own OpenAPI spec; the frontend keeps two clients in one
file, sharing axios setup but pointed at different `baseURL`s.

## Two specs, two type files

| Spec source | Owned by | Path | Output |
|-------------|----------|------|--------|
| Python `v1.yaml` | Agent A (hand-written) | `docs/api/v1.yaml` | `src/api/types.python.gen.ts` |
| Java `java-v1.yaml` | Agent D (springdoc auto-generated) | `docs/api/java-v1.yaml` | `src/api/types.java.gen.ts` |

Generation is `openapi-typescript` v7 (~3 MB, types-only — no fetch wrapper):

```bash
pnpm gen:api:python   # one spec
pnpm gen:api:java     # one spec
pnpm gen:api          # both
```

The two `*.gen.ts` files are **generated artifacts** — never hand-edit them.
Regenerate after every spec change.

## Choosing a client

```ts
import { pythonClient, javaClient } from "@/api/client";
import type { paths as PyPaths } from "@/api/types.python.gen";
import type { paths as JavaPaths } from "@/api/types.java.gen";

// Python: read agent memory events
type EventsResp =
  PyPaths["/api/v1/agents/{agent_id}/memory/events"]["get"]["responses"]["200"]["content"]["application/json"];

const events = await pythonClient.get<EventsResp>(
  `/api/v1/agents/${agentId}/memory/events`,
);

// Java: list plugins
type PluginListResp =
  JavaPaths["/api/v1/plugins"]["get"]["responses"]["200"]["content"]["application/json"];

const plugins = await javaClient.get<PluginListResp>("/api/v1/plugins");
```

Rule of thumb:

| Concern | Client |
|---------|--------|
| Memory / Soul / Identity / agent runtime / `/health` | `pythonClient` |
| Users / Sessions / Plugins / Connectors / Permissions / business CRUD | `javaClient` |

If a feature crosses both (e.g. start a session AND record memory) call each
client in sequence — they share the same auth token but not the same
transaction boundary.

## Environment overrides

| Variable | Default | Effect |
|----------|---------|--------|
| `VITE_PYTHON_API_BASE_URL` | `http://localhost:8000` | Python runtime base |
| `VITE_JAVA_API_BASE_URL` | `http://localhost:8080` | Java business base |
| `VITE_API_BASE_URL` | (none) | Legacy fallback for Python only — kept while we migrate |

In dev: `make dev` brings up both via docker-compose. In staging/prod the
URLs become subdomains (`api-py.agentcook.cc` / `api.agentcook.cc`) configured
through the environment variables above.

## Why two clients, not one BFF

We considered a single BFF that proxies both backends. Rejected for now
because:

- The two backends have different ownership cadence (A vs D); a BFF would
  become a third spec to coordinate
- Pact contracts already give us per-backend testing — a BFF would dilute that
- Phase 4 swarm gateway (Day 38+) is the natural place to introduce a unified
  edge; doing it now is premature

## Migrating from the deprecated untyped helpers

`get` / `post` / `put` / `del` named exports still work (forwarded to
`pythonClient` for backwards compatibility) but are marked `@deprecated`.
Replace them call-by-call with the typed client + a `paths` lookup:

```diff
- import { get } from "@/api/client";
- const data = await get<MemoryEvent[]>(`/agents/${id}/memory/events`);
+ import { pythonClient } from "@/api/client";
+ import type { paths } from "@/api/types.python.gen";
+ type Resp = paths["/api/v1/agents/{agent_id}/memory/events"]["get"]["responses"]["200"]["content"]["application/json"];
+ const data = await pythonClient.get<Resp>(`/api/v1/agents/${id}/memory/events`);
```

Migration target: end of Phase 3 (Day 37).

## Regenerate when

- Agent A pushes a new commit to `docs/api/v1.yaml`
- Agent D re-exports `docs/api/java-v1.yaml` (after any Controller/DTO change)
- CI: regenerate on every `main` push and fail PRs whose generated types differ
  from committed (Day 25+ to wire — for now manual `pnpm gen:api`)
