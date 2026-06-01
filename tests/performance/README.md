# Performance Testing

Owner: Agent C. Brought forward from the Phase 3 Day 31-33 static plan
to Day 30 (C had spare capacity after the Pact consumer/provider
double-side wrap-up shipped Day 29).

Two tools, three flows. Same flows, different tools, so the numbers
can sanity-check each other when one reports something surprising.

| Tool | Lang | Strength | When to reach for |
|---|---|---|---|
| `locust` | Python | live web UI, easy to script complex flows in Python | exploration, custom assertions |
| `k6` | JS (binary, written in Go) | strict perf model, CI/CD gates, ramp scenarios | regression baselines, threshold gates |

## Three flows (mirror the Day 27-29 e2e specs)

1. **Login** → `POST /api/v1/auth/login` (Java :8080)
2. **List users** → `GET /api/v1/users` (Java :8080, Authorization required)
3. **Stream a skill** → `POST /api/v1/skills/{id}/test/stream` (Python :8000, SSE)

## Running locust

`locust` is a dev dependency (added Day 30). Spin up the dev stack
first, then either headless or open the web UI.

```bash
# Dev stack up (Day 23 onwards)
make dev                              # postgres + redis + jaeger + ...
cd agentcook-java && ./mvnw -pl agentcook-api spring-boot:run &  # Java :8080
# Python :8000 lives in `make dev`.

# Smoke — 50 users / 5/s spawn / 60s
make perf-test-load
# or, web UI:
uv run locust -f tests/performance/locustfile.py
# → http://localhost:8089
```

Override hosts via env when pointing at staging or a remote stack:

```bash
LOCUST_JAVA_BASE=http://staging:8080 \
LOCUST_PYTHON_BASE=http://staging:8000 \
  uv run locust -f tests/performance/locustfile.py
```

## Running k6

k6 is a single static binary — **C does not install it on the host**
(Day 6 host-config redline). Install it yourself:

```bash
brew install k6
# or follow https://k6.io/docs/get-started/installation/
```

Then:

```bash
make perf-test-k6
# or, with explicit ramp:
K6_VUS=50 K6_DURATION=60s k6 run tests/performance/k6/login-flow.js
```

Phase 5 Day 50 will land a multi-stage scenario file
(`tests/performance/k6/ramp-50-100-200-500.js`) once the dev backends
are stable enough to baseline against. Today's `login-flow.js` proves
the rig.

## CI integration

These suites are **not** in `make ci-local`. Reasons:

- Performance tests need a stable baseline environment (a flaky run
  on a busy laptop tells you nothing about regressions).
- Sustained 50-VU load on the dev stack is rude during development.
- Phase 5 will land a dedicated `perf-baseline.yml` workflow that
  runs nightly on a quiescent runner. Until then, run by hand.

## Known gaps (Phase 5 Day 50-51 backlog)

- No SSE backpressure spec — locust's `iter_lines()` greedy-drains;
  real users wait between chunks. Day 50 will add a scenario with
  per-chunk think-time.
- No PG / Redis percentile capture — testcontainers ports change per
  run, but Day 50 will stand up a long-lived stack with Prometheus
  scraping the JVM and PG metrics.
- No Java app `/actuator/prometheus` GAP closure — depends on D
  adding `micrometer-registry-prometheus` (tracked in
  `audit/phase2-review-2026-06-01.md` §5 P0-1).
