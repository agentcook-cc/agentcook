# Observability — local dev SOP

Phase 2 Day 23 — Agent C.

This is the operator-facing brief: where traces / metrics land, how to
verify they're flowing, and how to read the result. ADR-005 owns the
selection rationale; this doc is the runbook.

## What's wired today

| Layer | Backend | Endpoint | UI | Status |
|---|---|---|---|---|
| Traces | Jaeger all-in-one (1.57) | OTLP gRPC `:4317` / HTTP `:4318` | `:16686` | ✅ Day 16+ |
| Metrics | Prometheus 2.53 | scrape via `scripts/prometheus.yml` | `:9090` | ✅ Day 18+ |
| Logs | structlog stdout | — | — | ✅ Day 19+ |
| LLM-specific | Langfuse | — | `:3000` | ⏸ Phase 4 Day 38 (image pull blocked) |

The Python runtime emits OpenTelemetry traces via
`agentcook_app.observability.setup_telemetry`, which auto-instruments
FastAPI and registers a `BatchSpanProcessor` exporting to OTLP gRPC.

## OTLP endpoint conventions

| Where the runtime is | `OTEL_EXPORTER_OTLP_ENDPOINT` value |
|---|---|
| Host machine (uvicorn directly) | `http://localhost:4317` |
| Inside docker-compose (Java/Python service container) | `http://jaeger:4317` |
| CI (no jaeger service container) | unset — SDK no-ops cleanly |

`make dev` injects the host value. The compose Java app section (Day 23
draft) injects the container-network value via `environment:`. Both are
correct for their context — don't unify them; container DNS doesn't
work from the host.

## Sampler

The OTel Python SDK default sampler is `ParentBased(root=AlwaysOn)` —
**100% sampling** without any explicit configuration. Local dev wants
this: trace volume is low, missing traces is more painful than seeing
all of them.

If you ever set `OTEL_TRACES_SAMPLER` (e.g. for staging), `parentbased_traceidratio` with a
fraction in `OTEL_TRACES_SAMPLER_ARG` is the supported pattern. The
sample rate decision lives entirely in the SDK; Jaeger all-in-one
accepts everything that arrives.

## Verifying end-to-end (the smoke test)

```bash
make dev                                      # brings up jaeger + agentcook
bash scripts/observability/verify-trace.sh    # one-shot trace check
```

What it does:

1. confirms Jaeger query API is reachable (`:16686/api/services`)
2. confirms agentcook `/health` responds (liveness only — used to assert
   the runtime is up, not as the trace probe)
3. snapshots trace count for `service=agentcook-python` over the last 1m
4. fires a `GET /__verify_trace__` (404, but still produces a server span;
   we avoid `/health` / `/openapi.json` / `/docs` because those substrings
   are in `excluded_urls` in `observability.py` — Day 23 A change — so they
   silently produce no spans by design)
5. waits 8s for `BatchSpanProcessor` to flush
6. asserts the trace count grew by ≥ `--min-spans` (default 1)

Override the probe path with `PROBE_PATH=/api/v1/something bash …` if you
need to exercise a real instrumented route.

### After Agent A's per-module spans land (Day 23+)

A's instrumentation adds spans inside `multi_agent` / `model_router` /
`mcp_adapter` / `memory` / `compaction`. Pass `--min-spans 5` to
require visible business spans, not just the FastAPI server span:

```bash
bash scripts/observability/verify-trace.sh --min-spans 5
```

Then open the Jaeger UI: `http://localhost:16686/search?service=agentcook-python`

You should see a tree like:

```
HTTP GET /api/v1/agents/{id}/run        (FastAPIInstrumentor server span)
├── multi_agent.loop                    (per agent_loop iteration)
│   ├── model_router.dispatch
│   │   └── model_call: claude-sonnet-4-6
│   └── mcp_adapter.tool_invoke: read_file
└── memory.read_from_layer: SOUL
```

## Troubleshooting

### `verify-trace.sh` exits 3 ("trace count did not grow")

Check in order:

1. `OTEL_EXPORTER_OTLP_ENDPOINT` matches the runtime's network context
   (see table above). The most common bug: copy-pasted `http://jaeger:4317` from
   compose into a host shell, where DNS doesn't resolve.
2. `setup_telemetry(app)` is invoked in `create_app()` (already wired
   Day 16). If someone removed it, add it back.
3. `opentelemetry-sdk` / `exporter-otlp-proto-grpc` /
   `instrumentation-fastapi` are all installed: `uv pip list | grep otel`.
4. `OTEL_TRACES_SAMPLER` is unset or set to `always_on` /
   `parentbased_traceidratio` with arg ≥ 0.5.

### Jaeger UI shows traces but missing parent-child links

The OTel propagator must match across services. Default for the SDK is
W3C tracecontext, which Java agentcook (when wired) and FastAPI both
use. Don't introduce B3 headers without changing both ends.

### Span data missing for `connector_open` / `tool_invoke` / `model_call`

Those spans live inside `agentcook-core` modules. They're emitted only
when A's Day 23 per-module instrumentation is in place. Re-run after
A's progress reports `core/instrumentation: ✅`.

## Ports cheat sheet

| Service | Port | UI |
|---|---|---|
| jaeger UI | 16686 | http://localhost:16686 |
| jaeger OTLP gRPC | 4317 | — |
| jaeger OTLP HTTP | 4318 | — |
| prometheus UI | 9090 | http://localhost:9090 |
| agentcook-python | 8000 | http://localhost:8000/docs |
| agentcook-java (Day 23+) | 8080 | http://localhost:8080/actuator/health |
