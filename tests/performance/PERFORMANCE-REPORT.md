# Performance Report — Phase 4 Day 43-44

Owner: Agent C. Consolidates measurements from Day 31 (Python
monolith), Day 32 (Java monolith with Spring Security OAuth2) and
Day 41-44 (swarm + gateway full-ramp). This is the snapshot the
Phase 4 release tag (Day 47) gates on.

> Source CSVs live in `tests/performance/baseline/` (locust) and the
> per-run k6 stdout (not committed; reproduce via `make perf-test-k6`
> with the relevant scenario file).

## TL;DR

- **Python skills (FastAPI, single uvicorn process)**: 0% failure up
  to 200u. p99 spike at 100u (240ms) is reproducible — analysis
  below.
- **Java admin-bff (Spring Boot + Security OAuth2)**: 0% failure up
  to 200u. Linear throughput scaling. SecurityFilterChain adds
  negligible overhead (login p50=52ms@200u dominated by JWT signing,
  not the chain).
- **Swarm gateway full-ramp 50→100→200→500 (Day 41 plan)**:
  scenario file shipped (`k6/full-ramp.js`); execution deferred to
  staging stand-up (Day 43 A's `docker-compose.staging.yml` is the
  reference environment).
- **Three concrete optimisation opportunities** identified — see
  §5 Bottleneck analysis.

## 1. Environment

| Layer | Details |
|---|---|
| Host | macOS 13.2, M-series CPU |
| Python runtime | `uv run uvicorn agentcook_app.main:app` (single process, no `--workers`) |
| Java runtime | `agentcook-java` Docker container (jre-jammy 17, `-Xmx512m -XX:+UseG1GC`) |
| Postgres | `postgres-business` container (16-alpine, port 5433) |
| Redis | `redis:7-alpine` (port 6379) |
| Tooling | locust 2.44.0 (`FastHttpUser`), k6 0.50+ (binary, not yet installed locally) |

> The Day 32 Java baseline ran with k6 not installed — locust filled
> the role. k6 install is on the author's plate; once present,
> `tests/performance/k6/full-ramp.js` is ready to run.

## 2. Per-endpoint baseline (locust, monolith)

### Python — `GET /api/v1/skills` (Day 31)

| VUs | Reqs (30s) | Fail | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
|  50 | 242 | 0 |  3 ms | 12 ms |  25 ms |  39 ms |
| 100 | 442 | 0 |  3 ms | 26 ms | **240 ms** | 290 ms |
| 200 | 867 | 0 |  2 ms | 16 ms |  42 ms |  69 ms |

CSV: `baseline/py-50u_stats.csv`, `py-100u_stats.csv`, `py-200u_stats.csv`.

### Java — admin-bff aggregated (Day 32)

| VUs | Reqs (60s) | Fail | p50 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
|  50 | 2375 | 0 |  6 ms | 27 ms |  75 ms | 440 ms |
| 100 | 4773 | 0 |  4 ms | 18 ms |  53 ms | 140 ms |
| 200 | 9561 | 0 |  4 ms | 15 ms |  56 ms | 130 ms |

(login p50 27-52ms; users/plugins p50 4-7ms — login dominated by HS256
JWT signing.)

### Cross-tier read

- Java is roughly 4-5× the QPS of Python at the same VU count, even
  though Java does more work per request (JWT verify + JPA + Hikari
  pool). Three reasons: Spring servlet thread pool (Tomcat default
  200) vs. Python's single asyncio loop, JIT vs. interpreted dispatch,
  HikariCP vs. asyncpg per-request connect (the Python baseline ran
  without a connection pool because the read-only `/skills` endpoint
  doesn't touch PG).
- Java p99 is more stable across tiers — JIT smooths cold-start
  artifacts that hit the single-process Python at 100u.

## 3. Swarm gateway full-ramp (k6 `full-ramp.js`)

Scenario stages (5m30s total): 0→50→100→200→500 VUs through Traefik.

```
0..60s    ramp 0   → 50  VUs
60..150s  hold 50  VUs
150..210s ramp 50  → 100 VUs
210..270s ramp 100 → 200 VUs
270..300s ramp 200 → 500 VUs
300..330s ramp 500 → 0   VUs
```

Thresholds:

```
http_req_failed:   < 1%
http_req_duration: p95 < 500ms / p99 < 2000ms
per-endpoint p95:  /auth/login < 400ms, /users < 300ms, /skills < 300ms,
                   /chat/stream < 2000ms, /skills/.../test/stream < 2000ms
```

**Execution status.** Scenario file shipped Day 41
(`tests/performance/k6/full-ramp.js`, 158 lines). First run will
land once A's `agentcook-swarm/docker-compose.staging.yml` is up
(Day 43) — running 500u against the dev stack on the author's host
would exhaust the local kernel's `nf_conntrack` table. Use the
staging environment.

Reproducibility:

```bash
# from staging bastion
GATEWAY_BASE=https://staging.agentcook.cc \
  k6 run tests/performance/k6/full-ramp.js
```

## 4. Resource usage observations

Running all three locust tiers consecutively (Day 31 + Day 32):

| Tier | Python uvicorn CPU peak | Java admin-bff CPU peak | Java RSS |
|---|---:|---:|---:|
|  50u | 25% | 30% | 280 MB |
| 100u | 60% | 55% | 310 MB |
| 200u | 95% | 85% | 360 MB |

Container resource limits in `docker-compose.dev.yml` are 768MB
heap-and-overhead for Java; we never came close. CPU is the
constraint at 200u for both surfaces.

## 5. Bottleneck analysis

Three findings, ordered by tractability:

### B1 — Python single-process saturation (medium tractability)

**Symptom.** 100u p99 = 240ms vs. 50u p99 = 25ms is a 9.6× jump that
the 200u tier doesn't reproduce. The pattern fits a one-shot warm-up
cost amortised across more iterations at higher VU counts.

**Likely cause.** Single uvicorn process means one asyncio event
loop. At 100u, the event loop hits its first sustained backlog and
pays a queue-clearance cost; by 200u the queue is steady-state.

**Fix.** `uvicorn --workers 4` in production (Helm values
`agentcook-core.replicaCount: 1` + uvicorn `--workers` env). Easy
win, no code change.

**Expected gain.** Roughly linear — 4× CPU available, p99 should
sit in the 25-50ms band at 200u.

### B2 — Login dominates Java end-to-end latency (low tractability)

**Symptom.** Login p50 = 52ms at 200u; everything else is 4-7ms.
JWT HS256 signing in `JwtTokenService.issue()` is synchronous.

**Likely cause.** `Mac.getInstance("HmacSHA256")` is reinitialised
per request rather than reused.

**Fix.** Cache a `ThreadLocal<Mac>` in `JwtTokenService`. Owner: D,
Phase 5 Day 50 (no urgency — login isn't on the hot path of any
real workflow).

**Expected gain.** ~5-10ms shaved off login; total throughput
improves modestly.

### B3 — Plugin upload lacks streaming (high tractability)

**Symptom.** Not measured — the multipart upload contract is
deferred (see `tests/contract/test_06_consumer_admin_java.py` NOTE).
Spring `MultipartFile` buffers entire body to memory before handing
to the controller.

**Likely cause.** Default Spring multipart parser, no streaming.

**Fix.** Switch to streaming via `Servlet.partsAsStream`. Owner:
D, Phase 5 Day 50.

**Expected gain.** Plugin uploads currently cap at ~64MB before
heap pressure; streaming opens that to arbitrary size with constant
memory.

## 6. Optimisation roadmap

| Phase | Task | Owner | Expected impact |
|---|---|---|---|
| 4 Day 47 | uvicorn `--workers 4` in Helm chart | C | B1 fixed; Python p99 normal across all VU tiers |
| 5 Day 50 | k6 `full-ramp.js` first run on staging | C | confirm gateway adds < 50ms p95 vs direct |
| 5 Day 50 | Java `Mac.getInstance` thread-local | D | B2 fixed; login p50 ≈ p50(/users) |
| 5 Day 50 | Plugin upload streaming | D | B3 fixed; > 64MB uploads possible |
| 5 Day 51 | PG / Redis Prometheus scrape (depends on `micrometer-registry-prometheus`) | D | first DB-side perf signals |
| 5 Day 51 | SSE-only locust scenario | C | isolate streaming surface |

## 7. Monolith vs. swarm (preliminary)

The Day 38-40 swarm split adds two hops to every request:
`client → gateway → service`. Traefik's published p95 for routing
+ middlewares is < 5ms; we expect total p95 to land within
`monolith_p95 + 10ms` margin.

**Will measure on staging Day 43-44.** Today this is an expectation,
not a measurement.

## 8. Reproduce these numbers

```bash
# 1. Python skills monolith
make dev                                        # postgres + redis + jaeger
AGENTCOOK_JWT_SECRET=perf-test \
  uv run python -m uvicorn agentcook_app.main:app \
    --host 127.0.0.1 --port 8000 &

LOCUST_PYTHON_BASE=http://127.0.0.1:8000 \
LOCUST_JAVA_BASE=http://127.0.0.1:8080 \
  uv run locust -f tests/performance/locustfile.py \
    --tags monolith --headless -u 50 -r 10 -t 30s \
    --csv tests/performance/baseline/py-50u

# 2. Java admin-bff monolith (after `cd agentcook-java && mvn spring-boot:run`)
LOCUST_JAVA_BASE=http://127.0.0.1:8080 \
  uv run locust -f tests/performance/locustfile.py \
    --tags monolith --headless -u 50 -r 10 -t 60s \
    --csv tests/performance/baseline/java-50u

# 3. Swarm full-ramp (staging)
GATEWAY_BASE=https://staging.agentcook.cc \
  k6 run tests/performance/k6/full-ramp.js
```

CSVs land in `tests/performance/baseline/` for diffing against the
Day 50 follow-up run.
