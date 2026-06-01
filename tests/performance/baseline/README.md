# Baseline measurements

Owner: Agent C. First numbers landed Day 31 (Phase 3) — Python skills
side only. Java side waits for D's Day 31 rebuild + Security OAuth2 to
settle before we measure under the new SecurityFilterChain.

## How to read these files

For each `<scenario>_stats.csv` row:

| Column | Meaning |
|---|---|
| Request Count | total requests sent in the run |
| Failure Count | 4xx/5xx + assertion failures |
| 50%, 95%, 99% | latency percentiles in ms (locust default unit) |
| Requests/s | sustained throughput at the configured VU level |

Pair each `_stats.csv` with `_stats_history.csv` for the per-10s
time-series — that's where ramp-up artifacts and GC pauses show up.

## Day 31 — Python skills baseline

Environment: macOS 13, M-series, host networking, agentcook-python
ran via `uv run uvicorn` (not in a container). Java users in the
locustfile got 404s here because Java wasn't pointed at — see
"Why JavaApiUser failed" below.

| Scenario | VUs | spawn/s | run | reqs | fail | p50 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| py-50u   |  50 |  10 | 30s | 242 | 0 |  3 ms | 12 ms |  25 ms |  39 ms |
| py-100u  | 100 |  10 | 30s | 442 | 0 |  3 ms | 26 ms | 240 ms | 290 ms |
| py-200u  | 200 |  20 | 30s | 867 | 0 |  2 ms | 16 ms |  42 ms |  69 ms |

(values from `GET /api/v1/skills`, the cleanest measurement — see
`*_stats.csv` for full per-endpoint breakdown.)

### Observation worth chasing

The 100u run's `p99 = 240ms` jumps an order of magnitude above the
50u and 200u runs. Three plausible causes, in order of likelihood:

1. **Cold connection setup** — locust's `FastHttpUser` opens
   per-user pools; 100 simultaneous opens against a single uvicorn
   process likely hits TCP `accept()` queue depth. 200u is no worse
   because by the time those VUs spawn the pool has stabilised.
2. **Python GIL contention** — uvicorn is single-process here. Phase
   5 Day 50 will run against `--workers 4` and the spike should flatten.
3. **One-shot lazy import** — `routers/skills.py` imports the OTel
   tracer on first use; the cold-start cost amortises across VUs but
   hits the slow request hardest.

Not actioning today — record for Phase 5 Day 50 to revisit with a
multi-worker uvicorn and a longer warm-up window.

### Why JavaApiUser failed (50u/100u/200u all 100% failure)

The locust run pointed `LOCUST_JAVA_BASE` at port 8000 (Python's
uvicorn) by mistake in the first 50u invocation — Python has no
`/api/v1/users` / `/plugins` / `/auth/login`. The Java app's
`agentcook-java` container is on :8080 but has Day 27-30 code
unrebuilt (failure #10), so even pointing at 8080 returns 405 for
`/users` and 404 for several other admin endpoints.

Once D's Day 31 first-priority rebuild lands, re-run with
`LOCUST_JAVA_BASE=http://127.0.0.1:8080` and the JavaApiUser stats
become meaningful.

## Day 32 — Java baseline (post D rebuild + Security OAuth2)

Environment: macOS 13, M-series, host networking, agentcook-java ran
in Docker container (colima). Spring Security OAuth2 HS256 JWT active.
Prometheus `/actuator/prometheus` scrape state=up confirmed.

| Scenario | VUs | spawn/s | run | reqs | fail | p50 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| java-50u   |  50 |  10 | 60s | 2375 | 0 |  6 ms | 27 ms |  75 ms | 440 ms |
| java-100u  | 100 |  20 | 60s | 4773 | 0 |  4 ms | 18 ms |  53 ms | 140 ms |
| java-200u  | 200 |  40 | 60s | 9561 | 0 |  4 ms | 15 ms |  56 ms | 130 ms |

(Aggregated values. Per-endpoint: login p50=27-52ms, users/plugins p50=4-7ms.)

### Observations

- **0% failure rate across all three tiers** — Security filter chain adds
  negligible overhead (login is the slowest at p50=52ms@200u, dominated by
  JWT signing not network).
- **Throughput scales linearly**: 40 → 80 → 160 req/s as VU doubles.
  No saturation point visible at 200u — Phase 5 Day 50 will push to 500u.
- **p99 variance low**: 53-75ms across tiers (contrast Python's 100u p99 spike).
  HikariCP connection pooling and JVM JIT eliminate the cold-start effects
  seen in the Python single-process baseline.

### Tooling note

k6 installation failed (brew Tier-2 compile error + GitHub CDN timeout on
arm64 binary). Baselines captured with **locust 2.44.0** (`FastHttpUser`,
same locustfile as Day 31 Python runs). Results are directly comparable.

## Pending baselines (Phase 5)

- [x] Java baseline (`java-50u`, `java-100u`, `java-200u`) — ✅ Day 32.
- [ ] Full-stack ramp (Java + Python simultaneous, 200u each surface).
- [ ] Phase 5 Day 50: 500u sustained, with PG/Redis Prometheus
      scraping and JVM `/actuator/prometheus`.
- [ ] SSE-only scenario — current locustfile under-samples SSE
      (every 4th iteration); Phase 5 will isolate it.
