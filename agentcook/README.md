# agentcook

FastAPI runtime for the agentcook Agent + Memory API. Composes
[`agentcook-core`](../agentcook-core) (protocols),
[`agentcook-providers`](../agentcook-providers) (LLM adapters), and
[`agentcook-storage`](../agentcook-storage) (PG / Redis / S3) into a
single HTTP service. Per **ADR-013** this Python service is the
*runtime* side of a dual-backend split — business CRUD (User /
Permission / Connector / AuditLog) lives in the Java service
[`agentcook-java`](../agentcook-java).

## What This Service Owns (vs. Java)

| Owned by `agentcook` (this package) | Owned by `agentcook-java` |
|-------------------------------------|---------------------------|
| Agent runtime endpoints (`/api/v1/chat/stream`, `/api/v1/agents/*/memory`) | User / Session / Plugin / Connector / Permission CRUD |
| Memory layer (Soul / events) — `agentcook-storage` backed | OAuth2 token issuance + JWKS rotation |
| Skills / Delegations / Logs internal routers | Audit Log persistence |
| LLM provider routing (Qwen default per ADR-016) | Spring Security filter chain + RBAC |
| JWT *verification* (not issuance) | JWT *issuance* + refresh-token flow |

The boundary is enforced by tests: contract tests in
`tests/contract/` pin the Python ↔ Java surface, and the OpenAPI
specs are split (`docs/api/v1.yaml` for Python — frozen 2026-06-07
at v1.2.0 — and `docs/api/java-v1.yaml` for Java).

## Install

```bash
pip install agentcook
# Also installs agentcook-core. Vendor extras for production:
pip install 'agentcook[postgres,qwen]'    # asyncpg + qwen-via-openai
```

## Running

### Local (uvicorn, single worker)

```bash
# 1. Configure (.env or shell):
export AGENTCOOK_LLM_PROVIDER=qwen          # or 'openai' / 'echo'
export QWEN_API_KEY=sk-...                  # required for real LLM path
export AGENTCOOK_JWT_SECRET=dev-only-do-not-use-in-prod
export DATABASE_URL=postgresql://agentcook:agentcook@localhost:5432/agentcook

# 2. Apply migrations:
uv run alembic upgrade head

# 3. Start:
uv run uvicorn agentcook_app.main:app --host 0.0.0.0 --port 8000
# Add --reload for dev; --workers N for prod CLI mode.
```

### Production (Helm chart — recommended)

The agent-core deployment in `deploy/helm/agentcook/` uses the
`agentcook-swarm/services/agent-core/main.py` entrypoint instead
(HTTP + gRPC concurrently for swarm mode). See
[`agentcook-swarm/README.md`](../agentcook-swarm) for that path.

### Mock mode (no LLM keys / contract tests / CI)

```bash
export AGENTCOOK_CHAT_MOCK=true
# /api/v1/chat/stream now returns canned SSE frames; everything else
# is identical. Read by chat.py:_use_mock() on every request.
```

## Routers

| Router | Mount | Spec section | Notes |
|--------|-------|--------------|-------|
| `memory` | `/api/v1/agents/{agent_id}/memory`, `/api/v1/agents/{agent_id}/soul` | Memory CRUD + soul versioning | Backed by `agentcook-storage` PgVectorMemoryStore |
| `chat` | `/api/v1/chat/stream` | SSE streaming chat (ADR-017) | Real Qwen via `agentcook-providers`; mock fallback via env |
| `skills` | `/api/v1/skills`, `/api/v1/skills/{id}/test/stream` | Skill catalog + test runner | Loaded via `agentcook-core.skill_loader` |
| `delegations` | `/api/v1/delegations`, `/api/v1/delegations/{id}/run` | Multi-agent orchestration | LangGraph-shaped state graphs |
| `logs` | `/api/v1/logs` (admin only) | Structured log query | structlog JSON + correlation-id |

Health (`/healthz`, `/readyz`), metrics (`/metrics`), and OpenAPI
(`/openapi.json`, `/docs`) live outside the versioned namespace
(`setup_health` / `setup_metrics` / `_install_freeze_metadata` in
`main.py`).

## Architecture (ADR-013 dual backend)

```
                         ┌──────────────────────┐
                         │  Frontend (admin/app) │
                         └──────────┬───────────┘
                                    │ HTTP + SSE
                ┌───────────────────┼───────────────────┐
                │                                       │
                ▼                                       ▼
     ┌──────────────────┐                  ┌──────────────────┐
     │  agentcook (this) │ ◄── JWT verify ─│ agentcook-java   │
     │  Python FastAPI   │   token issued  │  Java Spring Boot │
     │  Agent + Memory    │   by Java       │  Business CRUD    │
     └─────────┬─────────┘                  └──────────────────┘
               │
       ┌───────┼────────────┐
       ▼       ▼            ▼
  ┌────────┐ ┌────────┐ ┌────────┐
  │ Postgres│ │ Redis  │ │ Qwen / │
  │ pgvector│ │ cache  │ │ OpenAI │
  └────────┘ └────────┘ └────────┘
```

JWT verification config (`agentcook_app/security.py`):
- Dev: HS256 with `AGENTCOOK_JWT_SECRET`
- Prod: RS256 with `AGENTCOOK_JWT_PUBLIC_KEY` (rotated via Java's JWKS)

## Configuration (Environment Variables)

| Variable | Required | Default | Used by |
|----------|----------|---------|---------|
| `AGENTCOOK_LLM_PROVIDER` | for chat | (empty → mock) | chat router |
| `QWEN_API_KEY` / `DASHSCOPE_API_KEY` | for Qwen | — | agentcook-providers factory |
| `OPENAI_API_KEY` | for OpenAI | — | agentcook-providers factory |
| `AGENTCOOK_CHAT_MOCK` | no | unset | chat router (`true` forces mock generator) |
| `AGENTCOOK_JWT_SECRET` | dev | `dev-only-do-not-use-in-prod` | security.py |
| `AGENTCOOK_JWT_PUBLIC_KEY` | prod | — | security.py (preferred over secret) |
| `AGENTCOOK_JWT_ALG` | no | `HS256` (dev) / `RS256` (when pubkey set) | security.py |
| `AGENTCOOK_CORS_ORIGINS` | no | localhost:5173/5174/3000 | main.py CORS |
| `DATABASE_URL` | for memory | — | health.py + storage |
| `AGENTCOOK_LOG_LEVEL` | no | `INFO` | logging_config |
| OTel `OTEL_*` family | optional | — | observability.py (NoOp default) |
| Langfuse `LANGFUSE_*` family | optional | — | observability.py (NoOp default) |

## Database

`alembic/versions/0001_agents_soul_memory.py` is the only migration —
three tables (`agents` / `soul_versions` / `memory_events`) plus the
`vector` extension. Schema has been stable since Day 11; later API
MINOR bumps (v1.1 / v1.2) added new routers, not new columns.

```bash
uv run alembic upgrade head           # apply
uv run alembic upgrade head --sql     # dry-run SQL
uv run alembic current                # show current revision
```

## Testing

```bash
uv run pytest agentcook -q                         # main unit + integration
uv run pytest agentcook/tests/test_chat_stream.py  # SSE wire format
uv run pytest agentcook/tests/test_stream_real_response_metadata.py  # Phase 4.6 real-path metadata pin
```

Current baseline (Day 51 spot check): 612 tests collected across the
monorepo / 587 PASS on `agentcook` + core + providers + storage / 13
known skips (schemathesis ↔ FastAPI interop, tracked).

Contract tests with the Java service live in `tests/contract/` (8
Pact files + provider verification — 10 PASS / 2 xfail backlog).

## ADR References

| ADR | Topic |
|-----|-------|
| ADR-001 | Single Python source of truth for plugin spec |
| ADR-008 | Four-layer memory model |
| ADR-013 | **Java owns business backend** — this service is JWT verifier + Agent/Memory runtime only |
| ADR-016 | Default LLM provider = Qwen |
| ADR-017 | `/api/v1/chat/stream` integrates real LLM via `agentcook-providers.create_provider()` (Phase 4.6, 2026-06-01) |
