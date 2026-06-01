#!/usr/bin/env bash
# verify-trace.sh — Day 23 Agent C / A+C end-to-end trace verification.
#
# Confirms that running ONE request against the agentcook FastAPI shell
# produces span data visible in Jaeger. Doubles as a smoke test for the
# Day 23 OTel instrumentation Agent A is wiring up.
#
# Workflow:
#   1. assert docker-compose `jaeger` service is healthy
#   2. assert agentcook-python is running (host or container) on $AGENTCOOK_URL
#   3. snapshot Jaeger span count for service=agentcook-python (baseline)
#   4. fire a request that should produce ≥ 1 span
#   5. wait for BatchSpanProcessor flush (default ~5s)
#   6. assert span count grew by ≥ MIN_NEW_SPANS
#
# Usage:
#   bash scripts/observability/verify-trace.sh
#   bash scripts/observability/verify-trace.sh --min-spans 5     # post-A-instrumentation
#   AGENTCOOK_URL=http://localhost:8000 bash scripts/observability/verify-trace.sh
#
# Exit codes:
#   0  spans grew as expected
#   1  jaeger not healthy
#   2  agentcook unreachable
#   3  no new spans observed (instrumentation broken or sampler off)

set -euo pipefail

AGENTCOOK_URL="${AGENTCOOK_URL:-http://localhost:8000}"
JAEGER_URL="${JAEGER_URL:-http://localhost:16686}"
JAEGER_SERVICE="${JAEGER_SERVICE:-agentcook-python}"
# /__verify_trace__ doesn't exist (returns 404) but FastAPIInstrumentor
# still creates a server span for the request. We deliberately avoid the
# `health` / `openapi.json` / `docs` substrings excluded in
# observability.py — those would silently produce no spans.
PROBE_PATH="${PROBE_PATH:-/__verify_trace__}"
MIN_NEW_SPANS=1
FLUSH_WAIT_SECONDS=8

while [[ $# -gt 0 ]]; do
  case "$1" in
    --min-spans) MIN_NEW_SPANS="$2"; shift 2 ;;
    --flush-wait) FLUSH_WAIT_SECONDS="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 64 ;;
  esac
done

# ---------- 1. jaeger healthcheck ----------
if ! curl -sf "${JAEGER_URL}/api/services" >/dev/null; then
  echo "❌ jaeger query API unreachable at ${JAEGER_URL}" >&2
  echo "   try: docker compose -f docker-compose.dev.yml up -d jaeger" >&2
  exit 1
fi
echo "✅ jaeger query API reachable"

# ---------- 2. agentcook healthcheck ----------
if ! curl -sf "${AGENTCOOK_URL}/health" >/dev/null; then
  echo "❌ agentcook unreachable at ${AGENTCOOK_URL}/health" >&2
  echo "   try: make dev (or run uvicorn agentcook_app.main:app)" >&2
  exit 2
fi
echo "✅ agentcook /health responds"

# ---------- 3. baseline span count ----------
# Jaeger query API: /api/traces?service=X&limit=N&lookback=Nm
# Returns JSON with `data: [trace, ...]`. Counting traces (not spans) is
# good enough for a smoke test — if A's instrumentation works, traces grow.
#
# limit=2000: a busy dev jaeger easily exceeds the default 200, masking
#   any new traces as the result list saturates.
# lookback=1m: bounds the window so unrelated background traces don't
#   dominate the delta.
count_traces() {
  curl -sf "${JAEGER_URL}/api/traces?service=${JAEGER_SERVICE}&limit=2000&lookback=1m" \
    | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("data") or []))'
}
baseline=$(count_traces || echo 0)
echo "📊 baseline: ${baseline} traces in last 1m for service=${JAEGER_SERVICE}"

# ---------- 4. fire a request ----------
# 404 on a non-existent path still produces a FastAPIInstrumentor server
# span. We use this rather than `/health` because A's Day 23 instrumentation
# excludes `health,openapi.json,docs` from tracing (standard practice — we
# don't want healthcheck poll storms in the trace store).
echo "🔥 firing GET ${AGENTCOOK_URL}${PROBE_PATH} (expected 404)"
curl -s "${AGENTCOOK_URL}${PROBE_PATH}" -o /dev/null

# ---------- 5. wait for flush ----------
echo "⏳ waiting ${FLUSH_WAIT_SECONDS}s for BatchSpanProcessor flush"
sleep "${FLUSH_WAIT_SECONDS}"

# ---------- 6. assert growth ----------
after=$(count_traces || echo 0)
delta=$((after - baseline))
echo "📊 after: ${after} traces (delta=${delta}, required ≥ ${MIN_NEW_SPANS})"

if (( delta < MIN_NEW_SPANS )); then
  echo "❌ trace count did not grow by ≥ ${MIN_NEW_SPANS}" >&2
  echo "   common causes:" >&2
  echo "     - OTEL_EXPORTER_OTLP_ENDPOINT misconfigured (expected http://localhost:4317 on host, http://jaeger:4317 in compose)" >&2
  echo "     - sampler set to never_on / probability < 1.0" >&2
  echo "     - FastAPIInstrumentor not invoked in main.py" >&2
  exit 3
fi

echo "✅ trace verification PASSED — ${delta} new traces visible in Jaeger"
echo "   open the UI: ${JAEGER_URL}/search?service=${JAEGER_SERVICE}"
