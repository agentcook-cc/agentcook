# Installation

agentcook ships as a monorepo with three runtimes. Pick the surface(s) you
need.

## Prerequisites

| Tool | Min version | Used by |
|------|-------------|---------|
| Python | 3.11 | `agentcook-core`, `agentcook` FastAPI app |
| Java | 17 | `agentcook-java` business backend |
| Node.js | 20 LTS | `agentcook-admin`, `agentcook-app`, `docs-site` |
| pnpm | 9 | Frontend monorepo |
| Docker + Compose | latest | Dev stack (Postgres, Redis, Jaeger, Prometheus) |
| `uv` | 0.5+ | Python dependency resolver |

::: tip
On Apple Silicon Macs we test with Colima for Docker; Docker Desktop also
works. Don't run them in parallel — they fight over the same socket.
:::

## Python — `agentcook-core` + FastAPI

```bash
cd agentcook-cc
uv sync                                   # resolve all Python deps
uv run uvicorn agentcook_app.main:app --reload --port 8000
```

Health check: `curl http://localhost:8000/health` → `200 OK`.

## Java — `agentcook-java`

```bash
cd agentcook-cc/agentcook-java
./mvnw clean install -DskipTests          # compile only
./mvnw -pl agentcook-api spring-boot:run  # run the API
```

Health check: `curl http://localhost:8080/actuator/health` → `200 OK`.

## Frontends — admin + app

```bash
cd agentcook-cc
pnpm install                              # install all workspaces
pnpm --filter @agentcook-cc/admin dev     # → http://localhost:5174
pnpm --filter @agentcook-cc/app dev       # → http://localhost:5173
```

## Docker — full dev stack

```bash
cd agentcook-cc
make dev                                  # docker-compose up -d
```

This brings up Postgres, Redis, Jaeger, Prometheus, the Pact broker, and
the Java backend container.

## Verify

After `make dev` + the Python app:

```bash
curl localhost:8000/health           # → {"status":"ok"}
curl localhost:8080/actuator/health  # → {"status":"UP"}
curl localhost:16686/                # Jaeger UI
curl localhost:9090/                 # Prometheus UI
```

Continue to [Quickstart](/guide/quickstart) to send your first request.
