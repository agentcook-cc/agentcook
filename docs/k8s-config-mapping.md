# K8s Config Mapping — agentcook-java

Maps every configuration knob in `application.yml` / `application-k8s.yml`
to its K8s source (ConfigMap, Secret, or hard-coded). Pair with the
`Deployment` in `deploy/helm/agentcook/templates/` to wire env vars.

## Rule of thumb

- **ConfigMap** — non-sensitive, environment-shaped values (URLs, hosts,
  timeouts, log levels, feature flags). Safe to print in `kubectl
  describe` and to commit example values in the chart.
- **Secret** — anything that would let an attacker forge identity or
  read the database: DB password, JWT signing secret, OAuth client
  secrets, third-party API keys.
- **Hard-coded in image** — pure code defaults (`server.port: 8080`,
  `spring.jpa.hibernate.ddl-auto: validate`). These don't vary across
  environments, so don't pay the indirection cost.

## ConfigMap (`agentcook-java-config`)

| Env var | application property | Default | Notes |
|---|---|---|---|
| `SPRING_PROFILES_ACTIVE` | — | `k8s` | Activates `application-k8s.yml` |
| `POSTGRES_HOST` | `spring.datasource.url` | `postgres.default.svc.cluster.local` | K8s in-cluster DNS |
| `POSTGRES_PORT` | `spring.datasource.url` | `5432` | |
| `POSTGRES_DB` | `spring.datasource.url` | `agentcook_business` | |
| `POSTGRES_USER` | `spring.datasource.username` | `agentcook` | Read-only username is OK in ConfigMap |
| `REDIS_HOST` | `spring.data.redis.host` | `redis.default.svc.cluster.local` | |
| `REDIS_PORT` | `spring.data.redis.port` | `6379` | |
| `PYTHON_UPSTREAM_URL` | `agentcook.python-upstream-url` | `http://agent-core.default.svc.cluster.local:8000` | gRPC client target |
| `GRPC_SERVER_PORT` | `grpc.server.port` | `9090` | |
| `AGENTCOOK_AUTH_JWT_TTL_SECONDS` | `agentcook.auth.jwt-ttl-seconds` | `3600` | Token lifetime; non-sensitive |

## Secret (`agentcook-java-secret`)

| Env var | application property | Required | Notes |
|---|---|:---:|---|
| `POSTGRES_PASSWORD` | `spring.datasource.password` | ✅ | Rotate via `kubectl rollout restart deployment/agentcook-java` |
| `AGENTCOOK_AUTH_JWT_SECRET` | `agentcook.auth.jwt-secret` | ✅ | ≥ 32 bytes for HS256. Phase 4 Day 33-34 swaps for JWKS — Secret goes away. |

## Probe endpoints (no Secret/ConfigMap needed)

K8s probes hit these directly via the Pod's port 8080:

| Probe | Path | Spring Boot config |
|---|---|---|
| `livenessProbe` | `/actuator/health/liveness` | `management.endpoint.health.probes.enabled=true` |
| `readinessProbe` | `/actuator/health/readiness` | same |
| Prometheus scrape | `/actuator/prometheus` | `management.prometheus.metrics.export.enabled=true` |

Gate `readinessProbe` on dependencies (Postgres reachable, Flyway
migrated). `livenessProbe` should only fail on irrecoverable state — a
DB hiccup shouldn't restart the pod.

## Sample Helm `values-k8s.yaml`

```yaml
javaBackend:
  image: ghcr.io/agentcook/agentcook-java:1.0.0
  replicas: 2

  configMap:
    SPRING_PROFILES_ACTIVE: k8s
    POSTGRES_HOST: postgres.default.svc.cluster.local
    POSTGRES_DB: agentcook_business
    POSTGRES_USER: agentcook
    REDIS_HOST: redis.default.svc.cluster.local
    PYTHON_UPSTREAM_URL: http://agent-core.default.svc.cluster.local:8000

  secretRef:
    name: agentcook-java-secret
    keys:
      - POSTGRES_PASSWORD
      - AGENTCOOK_AUTH_JWT_SECRET

  probes:
    liveness:
      path: /actuator/health/liveness
      initialDelaySeconds: 30
      periodSeconds: 10
    readiness:
      path: /actuator/health/readiness
      initialDelaySeconds: 15
      periodSeconds: 5
```

## Rotation playbook

1. **JWT secret rotation** — new Secret, `kubectl rollout restart
   deployment/agentcook-java`. Tokens issued by the old secret reject
   on first auth check after restart; admin users re-login.
2. **DB password rotation** — coordinate with Postgres (`ALTER USER ...
   PASSWORD ...`), update Secret, rollout. Hikari pool refreshes
   connections; brief 5xx blip during failover.
