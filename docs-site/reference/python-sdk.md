# Python SDK Reference

The Python surface lives in two packages.

| Package | Purpose |
|---------|---------|
| `agentcook-core` | Pure-Python library — memory, plugins, model routing, hooks, sandbox. |
| `agentcook` | FastAPI app that exposes the runtime over HTTP. |

This page documents the most commonly imported symbols. The authoritative
spec is the OpenAPI document at `docs/api/v1.yaml` (also served live at
`http://localhost:8000/openapi.json`).

## `agentcook_core` — runtime primitives

### Memory

```python
from agentcook_core.memory import MemoryManager, MemoryLayer

mgr = MemoryManager(store=PgVectorMemoryStore(...))
await mgr.write_to_layer(MemoryLayer.SOUL, key="persona", content="...")
hits = await mgr.semantic_search("what did the user prefer last week?", top_k=5)
```

Four layers:

- **IDENTITY** — immutable card loaded from YAML at boot
- **SOUL** — agent's long-term persona / preferences
- **MEMORY** — event log with semantic search
- **DIARY** — per-session scratchpad

### Compaction & Pruning

```python
from agentcook_core.compaction import SummaryCompaction
from agentcook_core.pruning import RelevancePruning

cmp = SummaryCompaction(model_router=router, threshold_tokens=8000)
messages = await cmp.compact(messages) if cmp.should_compact(messages, ctx_window) else messages
messages = RelevancePruning().prune(messages)
```

Context-management primitives that keep long conversations inside the
model's context window. See ADR-012 for design rationale.

### Hooks

```python
from agentcook_core.hook_runtime import HookRegistry, HookEvent

@registry.on(HookEvent.MODEL_CALL, priority=10)
async def trace_model_call(ctx):
    print("calling", ctx.attrs["model.name"])
    yield                      # post-hook resumes here
    print("done in", ctx.attrs["duration_ms"], "ms")
```

Onion-model pre/post pipeline. 7 event types — see `HookEvent`.

### Plugin sandbox

```python
from agentcook_core.plugin_loader import load_plugin
from agentcook_core.sandbox_runner import SandboxRunner

manifest = load_plugin("./hello-echo.zip")
runner = SandboxRunner(image="python:3.11-slim", permissions=manifest.permissions)
result = await runner.invoke(manifest, payload={"message": "hi"})
```

Docker-isolated, capability-gated tool execution.

## `agentcook` — FastAPI endpoints

All endpoints live under `/api/v1`. Most require `Authorization: Bearer TOKEN` (issued by the Java auth controller).

| Path | Method | What |
|------|--------|------|
| `/agents/{id}/identity` | GET | Read identity card |
| `/agents/{id}/memory/events` | GET, POST | List / append memory events |
| `/agents/{id}/memory/search` | POST | Semantic search |
| `/agents/{id}/memory/flush` | POST | Erase memory (preserves IDENTITY/SOUL by default) |
| `/agents/{id}/soul` | GET, POST | Read / update soul layer |
| `/agents/{id}/soul/history` | GET | Soul layer changelog |
| `/skills` | GET | List registered skills |
| `/skills/{id}` | GET | Skill detail |
| `/skills/{id}/test/stream` | POST | SSE: stream-test a skill |
| `/agent/chat` | POST | SSE: agent conversation |
| `/health` | GET | Liveness |
| `/health/ready` | GET | Readiness (DB + Redis) |

The OpenAPI document includes full schemas, examples, and validation
rules. Generate typed clients with `openapi-typescript` for any
language — the admin and app frontends do exactly that
(`pnpm gen:api:python`).

## Environment variables

| Variable | Default | Effect |
|----------|---------|--------|
| `AGENTCOOK_DATABASE_URL` | `postgresql://localhost:5432/agentcook` | Memory + identity store |
| `AGENTCOOK_REDIS_URL` | `redis://localhost:6379/0` | Cache + rate-limit |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Trace export |
| `LANGFUSE_HOST` | — | Optional LLM observability |
| `OPENAI_API_KEY` / `QWEN_API_KEY` / `ANTHROPIC_API_KEY` | — | Provider credentials |
