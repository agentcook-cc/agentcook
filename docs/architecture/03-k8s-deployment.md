# 03 — Kubernetes Deployment (Helm chart, Phase 4)

The production deployment topology of `agentcook-cc` on Kubernetes,
fronted by Cloudflare DNS + Traefik Ingress. The Helm chart lives at
[`deploy/helm/agentcook/`](../../deploy/helm/agentcook) — 11 templates
managed by Agent C. This document describes the runtime shape;
C's [`docs/devops/`](../devops) is the operational reference.

```mermaid
flowchart LR
    User((User<br/>Browser))
    CF[Cloudflare<br/>DNS + WAF + Pages]
    subgraph K8s["Kubernetes Cluster"]
        direction TB
        Ing["Ingress<br/>(Traefik)<br/>:443"]
        subgraph Svc["Services + Deployments"]
            direction LR
            subgraph FE["Frontend tier"]
                Admin["admin-static<br/>nginx + Vue dist<br/>replicas: 2"]
                App["app-static<br/>nginx + React dist<br/>replicas: 2"]
            end
            subgraph Py["Python tier"]
                AC["agent-core<br/>Python FastAPI<br/>+ gRPC :50051<br/>replicas: 1"]
                Conn["connector<br/>Python FastAPI<br/>:8082<br/>replicas: 1"]
            end
            subgraph Jv["Java tier"]
                Bff["admin-bff<br/>Spring Boot<br/>:8080 + gRPC :9090<br/>replicas: 1<br/>JVM heap 768Mi"]
            end
        end
        subgraph Data["Stateful + Observability"]
            direction TB
            PG[(PostgreSQL<br/>+ pgvector)]
            Redis[(Redis)]
            Etcd[(etcd<br/>service discovery)]
            OTel["OTel Collector"]
            Jaeger["Jaeger"]
            Prom["Prometheus"]
            Loki["Loki"]
            Graf["Grafana"]
        end
    end
    Langfuse[Langfuse Cloud<br/>SaaS]
    Qwen[Qwen DashScope]

    User --> CF
    CF --> Ing
    Ing --> Admin
    Ing --> App
    Admin -->|REST + SSE| AC
    Admin -->|REST| Bff
    App -->|REST + SSE| AC
    App -->|REST| Bff
    Bff -->|gRPC :50051| AC
    AC -->|HTTPS| Qwen
    AC --> PG
    AC --> Redis
    AC --> Etcd
    Conn --> Etcd
    Bff --> PG
    AC -->|OTLP gRPC :4317| OTel
    Conn --> OTel
    Bff --> OTel
    OTel --> Jaeger
    OTel --> Prom
    AC -->|HTTPS| Langfuse
    Bff -->|Promtail| Loki
    AC --> Loki
    Prom --> Graf
    Loki --> Graf
    Jaeger --> Graf

    classDef edge fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef python fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef java fill:#f9fbe7,stroke:#827717,stroke-width:2px
    classDef fe fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef data fill:#fce4ec,stroke:#880e4f,stroke-width:1px
    classDef ext fill:#e8eaf6,stroke:#1a237e,stroke-width:1px,stroke-dasharray: 5 5
    class CF,Ing edge
    class AC,Conn python
    class Bff java
    class Admin,App fe
    class PG,Redis,Etcd,OTel,Jaeger,Prom,Loki,Graf data
    class Langfuse,Qwen ext
```

## Helm Chart Layout

```
deploy/helm/agentcook/
├── Chart.yaml
├── values.yaml                     # default (dev / staging)
├── values-staging.yaml             # staging overrides
├── values-prod.yaml                # prod overrides (Phase 4.5 P2)
└── templates/
    ├── _helpers.tpl                # common labels / fullname
    ├── deployment-agent-core.yaml  # Python agent-core
    ├── deployment-connector.yaml   # Python connector
    ├── deployment-frontend.yaml    # admin-static + app-static
    ├── deployment-java.yaml        # admin-bff (D + C cross-cutting)
    ├── configmap.yaml              # env vars (non-secret)
    ├── secret.yaml                 # JWT + LLM API keys
    ├── service.yaml                # ClusterIP services for each
    ├── ingress.yaml                # Traefik routes
    ├── hpa.yaml                    # HorizontalPodAutoscaler
    └── pdb.yaml                    # PodDisruptionBudget
```

11 templates × default values render with `helm template` (no apply
needed) — see C's `docs/devops/k8s-operations-manual.md` for the
install + upgrade flow.

## Networking

| Edge | Path | Backend |
|------|------|---------|
| `agentcook.cc` | Cloudflare Pages | docs-site (VitePress, separate Pages project) |
| `staging.agentcook.cc` | K8s Ingress → staging namespace | full stack |
| `demo.agentcook.cc` | K8s Ingress → prod namespace (deferred to Phase 5+) | Blue-Green via Helm |
| `aquarium-writer-extending-thumbs.trycloudflare.com` | `cloudflared tunnel` → localhost:8000 | Phase 5 dev demo, not K8s |

Internal service-to-service stays inside the cluster:
`admin-bff` calls `agent-core` via gRPC at `agent-core:50051`, never
via the Ingress. etcd at `etcd:2379` handles dynamic discovery for
the swarm `agentcook_swarm/registry.py` lookups.

## Scaling

The Phase 4 chart sets `replicaCount: 1` on every Deployment. HPA
template is shipped but disabled by default. Day 50 performance work
proposed Helm-level scaling for `agent-core` to address the
single-worker uvicorn bottleneck:

> Use `agentCore.replicaCount: 1 → 4` (one worker per pod). Do **not**
> add `extraArgs: ["--workers", "4"]` — the swarm agent-core entrypoint
> uses `uvicorn.Server.serve()` programmatic API + same-process gRPC,
> which can't multiplex workers.

See `_internal/progress/progress-agent-a-day-52-54.md` reverse
fact-check section for the full reasoning + tradeoffs vs the
single-process `agentcook` shell that C measured locally.

## Stateful Dependencies

| Service | Persistence | Backup | Owner |
|---------|-------------|--------|-------|
| PostgreSQL + pgvector | PVC; managed PG in prod | nightly snapshot (cloud provider) | A (schema) + C (cluster) |
| Redis | optional persistence (AOF in prod) | not backed up (cache) | C |
| etcd | PVC | snapshot via `etcdctl snapshot save` | C |
| Loki (logs) | PVC; 7-day retention | not backed up | C |
| Prometheus | PVC; 14-day retention | not backed up | C |

Phase 5 backlog: Postgres backup automation runbook (currently relies
on cloud provider's default; needs explicit drill).

## Observability Flow

1. **Traces** — every Python service installs the OTel SDK on startup
   via `setup_telemetry()`; spans flow OTel Collector → Jaeger.
2. **Metrics** — `/metrics` endpoint on each service scraped by
   Prometheus; Grafana dashboards in `agentcook-swarm/grafana/`.
3. **Logs** — structlog JSON to stdout → Promtail tail → Loki →
   Grafana for query.
4. **LLM observability** — `agentcook_swarm/services/agent-core/
   langfuse_adapter.py` reports `generation` records to Langfuse
   Cloud via HTTPS; SaaS not in-cluster.

Required Helm `values.yaml` `observability:` block populates the
OTel + Langfuse env vars on every deployment template.

## Blue-Green Deployment (ADR-006)

`deploy/helm/agentcook/` supports two release labels (`blue` and
`green`) for cutover. The mechanics:

1. `helm install agentcook-prod-blue` (current live)
2. `helm install agentcook-prod-green` (new version)
3. Traefik Ingress weight shift: `0% → 50% → 100%` to green
4. `helm uninstall agentcook-prod-blue` after canary window

**Phase 4.5 deferred**: real production cutover is deferred to the
tutorial-publish window (P2 in roadmap). Phase 5 buffer time
includes re-running `audit/phase5-day50-performance-report.md`'s
4-tier baseline against the staging stack before the prod switch.

## ADR References

| ADR | Topic |
|-----|-------|
| ADR-005 | Observability stack (OTel + Prom + Loki + Jaeger + Grafana) |
| ADR-006 | Blue-Green deployment strategy |
| ADR-013 | Java owns business backend (`admin-bff` separate Deployment) |
| ADR-014 | gRPC bridge (`agent-core:50051` ← `admin-bff` calls) |

For operations procedures (`helm install` / `upgrade` / `rollback` /
troubleshooting), see [`../devops/`](../devops) — C's runbooks.
