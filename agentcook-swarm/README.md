# agentcook-swarm

Microservice deployment of the agentcook stack. The single-process
[`agentcook`](../agentcook) shell is split into four containers
behind a Traefik gateway, with the full observability triple
(Jaeger + Prometheus + Loki) and a shared Postgres / Redis / etcd
backing layer. Phase 4 introduced this layout; Phase 4.6 added
real-LLM chat (ADR-017) to the `agent-core` service.

## Service Topology

| Service | Responsibility | Port | Tech | Source |
|---------|----------------|------|------|--------|
| **gateway** | Traefik ingress + routing + rate limit | `:80` / `:443` | Traefik v3 | `gateway/` |
| **agent-core** | Chat / Stream + LLM routing + Memory + gRPC bridge | `:8000` (HTTP) + `:50051` (gRPC) | Python FastAPI + grpcio | `services/agent-core/` |
| **connector** | Plugin sandbox runner + external integrations | `:8082` | Python FastAPI | `services/connector/` |
| **admin-bff** | Business CRUD (User / Plugin / Session / Connector / Permission) | `:8080` (HTTP) + `:9090` (gRPC) | Java Spring Boot | `agentcook-java/` (sibling repo) |
| **admin-static** | Vue 3 admin dashboard | `:80` (behind gateway) | nginx + dist | `services/admin-static/` |
| **app-static** | React 19 chat app | `:80` (behind gateway) | nginx + dist | `services/app-static/` |

Backing services in the compose stack: PostgreSQL (with pgvector),
Redis, etcd (service discovery), Jaeger, Prometheus, Grafana, Loki,
Promtail, OTel Collector.

## Three Ways to Run It

### 1. Single-host swarm (`docker-compose.swarm.yml`)

Minimal compose for local end-to-end smoke testing.

```bash
docker-compose -f docker-compose.swarm.yml up -d
# 4 services + gateway; observability disabled to keep RAM low.
```

### 2. Full staging stack (`docker-compose.staging.yml`)

15 services including the full observability triple — what Day 41-44
landed and what `scripts/staging-smoke.sh` exercises.

```bash
docker-compose -f docker-compose.staging.yml up -d
./scripts/staging-smoke.sh   # HTTP health × 7 + Jaeger services + Prometheus targets + Loki + Grafana
```

Required environment variables for the staging stack are documented in
`docker-compose.staging.yml` comments — at minimum `QWEN_API_KEY`,
`AGENTCOOK_JWT_SECRET`, and `DATABASE_URL`.

### 3. Kubernetes via Helm (`../deploy/helm/agentcook/`)

The production deployment path. See
[`../deploy/helm/agentcook/`](../deploy/helm/agentcook) for the chart
(11 templates: `deployment-{agent-core,connector,frontend,java}`,
`service`, `ingress`, `configmap`, `secret`, `hpa`, `pdb`,
`_helpers.tpl`). C maintains the chart — refer to that directory's
`values.yaml` + `templates/` for the full surface.

> **agent-core deployment note** (relevant to A↔C handoff): the
> agent-core image entrypoint is
> `agentcook-swarm/services/agent-core/main.py`, which boots HTTP +
> gRPC in the same process via `uvicorn.Server(config).serve()` and
> `asyncio.create_task(start_grpc_server())`. This **cannot run with
> `uvicorn --workers > 1`** (programmatic Server API doesn't support
> multi-worker; same-process gRPC would also duplicate etcd
> registrations and bind-collide on `:50051`). For horizontal scale,
> use Helm `agentCore.replicaCount` (one worker per pod) — not
> `extraArgs: ["--workers", "4"]`. See
> `_internal/progress/progress-agent-a-day-52-54.md` reverse
> fact-check for the full reasoning behind this guidance.

## Observability (Day 41-44)

Each Python service boots the OTel SDK at startup and installs both
the tracing adapter (`tracing.py`) and the Langfuse adapter
(`langfuse_hook.py`) into `agentcook-core`:

```
agent-core / connector       core spans (tracing Protocol)
       │                            │
       ▼                            ▼
   setup_telemetry()  ────►  otel_tracer_adapter.install()
       │                            │
       ▼                            ▼
   OTel SDK              langfuse_adapter.install()
       │
       ▼
  OTel Collector ──►  Jaeger / Prometheus / Loki
```

Dashboards land in `grafana/dashboards/`:
- `overview.json` — request volume / error rate / p95 / p99 / status codes
- `llm-metrics.json` — LLM calls / tokens / estimated cost / latency by provider
- `service-health.json` — service up/down / CPU / mem / gRPC rates

Required env vars (all optional — telemetry degrades to NoOp without
them):

```
OTEL_SERVICE_NAME            agent-core | connector | admin-bff
OTEL_EXPORTER_OTLP_ENDPOINT  http://otel-collector:4317
LANGFUSE_HOST                https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
LANGFUSE_ENABLED             true | false (force NoOp without unsetting keys)
```

## gRPC Bridge (ADR-014)

`agent-core` exposes a gRPC server on `:50051` carrying
`ChatService.StreamChat` + Health + Reflection. The Java
`admin-bff` calls it via the generated `cc.agentcook.api.grpc.chat`
client to reach the Python LLM path from Java endpoints. Proto
sources live in `agentcook-java/proto/` (single source of truth for
both languages; the swarm Python build re-generates the stubs at
container build time — see
`services/agent-core/Dockerfile` proto-builder stage).

## Service Discovery (etcd)

`services/agent-core/etcd_registry.py` registers each service on
startup with a 30 s TTL keepalive and discovers peers via watch.
The compose / Helm stacks bring up etcd at `etcd:2379`. Local dev
without etcd falls back to the static endpoint table baked into
`agentcook_swarm/registry.py` (no extra config needed).

## ADR References

| ADR | Topic | Affects |
|-----|-------|---------|
| ADR-005 | OTel-shaped observability stack with Jaeger + Prometheus + Loki | all services |
| ADR-006 | Blue-Green deployment with Helm-managed traffic switch | `deploy/helm/agentcook/` |
| ADR-013 | Java owns business backend (admin-bff) | `admin-bff` lives in `agentcook-java`, not in `services/` |
| ADR-014 | gRPC bridge between Python `agent-core` and Java `admin-bff` | `services/agent-core/grpc_server.py` + `proto/` |
| ADR-016 | Default LLM provider = Qwen | `services/agent-core/` reads `AGENTCOOK_LLM_PROVIDER` |
| ADR-017 | `/api/v1/chat/stream` real-LLM integration (Phase 4.6) | `services/agent-core/` — `agentcook` package shares chat.py |

## Operations

For DevOps procedures (Helm install / upgrade / rollback /
troubleshooting), see [`../docs/devops/`](../docs/devops) — C's
DevOps documentation tree (Day 52-54).

## Status (Phase 5)

- ✅ Phase 4 compose stack stable (Day 41-44)
- ✅ Phase 4.6 chat real-LLM integration shipped (2026-06-01)
- 🟡 Phase 4.5 Blue-Green production rollout deferred to tutorial-publish window (P2 in roadmap)
- 🟡 prod baseline performance re-run pending Phase 5 buffer
  (see `audit/phase5-day50-performance-report.md` for the deferred plan)
