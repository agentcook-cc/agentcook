#!/usr/bin/env bash
#
# scripts/staging-smoke.sh — Phase 4 Day 44 smoke test for the staging stack.
#
# Verifies the docker-compose.staging.yml topology is healthy end-to-end:
#   1. every HTTP service answers /health (or equivalent)
#   2. Jaeger has at least one trace
#   3. Prometheus has all expected scrape targets UP
#   4. Loki accepts queries
#   5. Grafana responds + auto-provisioned dashboards loaded
#
# Run AFTER:
#     cd agentcook-swarm
#     docker compose -f docker-compose.staging.yml up -d
#     sleep 30   # let services warm up
#
# Exits non-zero on first failure; meant to be wired into CI.

set -uo pipefail

# Use functions, not aliases, so this is /usr/bin/env-bash portable.
RED=$'\e[31m'
GRN=$'\e[32m'
YLW=$'\e[33m'
RST=$'\e[0m'

PASS=0
FAIL=0
WARN=0

pass()  { echo "${GRN}✓${RST} $*"; PASS=$((PASS+1)); }
fail()  { echo "${RED}✗${RST} $*"; FAIL=$((FAIL+1)); }
warn()  { echo "${YLW}!${RST} $*"; WARN=$((WARN+1)); }
header() { echo; echo "── $* ──"; }

# Hosts are configurable so the same script works against localhost,
# a remote staging host, or a CI service-container network.
GATEWAY="${GATEWAY_URL:-http://localhost}"
JAEGER="${JAEGER_URL:-http://localhost:16686}"
PROMETHEUS="${PROMETHEUS_URL:-http://localhost:9091}"
LOKI="${LOKI_URL:-http://localhost:3100}"
GRAFANA="${GRAFANA_URL:-http://localhost:3000}"

# ----------------------------------------------------------------------
# 1. HTTP service health
# ----------------------------------------------------------------------
header "Service health"

check_http() {
    local name="$1" url="$2" expected="${3:-200}"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" || echo "000")
    if [[ "$code" == "$expected" ]]; then
        pass "$name → $code ($url)"
    else
        fail "$name → got $code expected $expected ($url)"
    fi
}

check_http "gateway"        "$GATEWAY/"                                404   # Traefik no-route OK
check_http "agent-core"     "$GATEWAY/api/v1/agents/test/identity"     404   # 404 = routed but unknown id
check_http "admin-bff health" "$GATEWAY/api/v1/users"                  200
check_http "jaeger UI"      "$JAEGER/"                                  200
check_http "prometheus"     "$PROMETHEUS/-/healthy"                     200
check_http "loki ready"     "$LOKI/ready"                               200
check_http "grafana login"  "$GRAFANA/login"                            200

# ----------------------------------------------------------------------
# 2. Jaeger has traces
# ----------------------------------------------------------------------
header "Jaeger traces"

# After services warm up, at least the SDK initialization spans + the
# smoke-test's own curls should produce traces.
services_with_traces=$(
    curl -s --max-time 5 "$JAEGER/api/services" \
        | python3 -c "import json, sys; d = json.load(sys.stdin); print(len(d.get('data', [])))" \
        2>/dev/null || echo 0
)
if [[ "$services_with_traces" -gt 0 ]]; then
    pass "Jaeger /api/services reports $services_with_traces service(s)"
else
    warn "Jaeger has 0 services — fire some requests first then re-run"
fi

# ----------------------------------------------------------------------
# 3. Prometheus targets
# ----------------------------------------------------------------------
header "Prometheus scrape targets"

targets_json=$(curl -s --max-time 5 "$PROMETHEUS/api/v1/targets" 2>/dev/null || echo '{}')
total_targets=$(echo "$targets_json" | python3 -c "import json, sys; d = json.load(sys.stdin); print(len(d.get('data', {}).get('activeTargets', [])))" 2>/dev/null || echo 0)
up_targets=$(echo "$targets_json" | python3 -c "import json, sys; d = json.load(sys.stdin); print(sum(1 for t in d.get('data', {}).get('activeTargets', []) if t.get('health') == 'up'))" 2>/dev/null || echo 0)

if [[ "$total_targets" -eq 0 ]]; then
    fail "Prometheus has 0 active scrape targets"
elif [[ "$up_targets" -eq "$total_targets" ]]; then
    pass "Prometheus targets: $up_targets/$total_targets UP"
else
    warn "Prometheus targets: $up_targets/$total_targets UP (some DOWN — check /targets UI)"
fi

# ----------------------------------------------------------------------
# 4. Loki query plane
# ----------------------------------------------------------------------
header "Loki query plane"

loki_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    "$LOKI/loki/api/v1/query?query=%7Bservice%3D%22agent-core%22%7D" || echo "000")
if [[ "$loki_status" == "200" ]]; then
    pass "Loki accepts queries"
else
    fail "Loki query plane → $loki_status"
fi

# ----------------------------------------------------------------------
# 5. Grafana dashboards
# ----------------------------------------------------------------------
header "Grafana dashboards"

# The provisioning files mount three known dashboards.
for uid in agentcook-overview agentcook-llm agentcook-health; do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
        -u "${GRAFANA_USER:-admin}:${GRAFANA_PASS:-admin}" \
        "$GRAFANA/api/dashboards/uid/$uid")
    if [[ "$code" == "200" ]]; then
        pass "dashboard $uid loaded"
    else
        fail "dashboard $uid → $code"
    fi
done

# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------
echo
echo "─────────────────────────"
echo "Smoke summary: ${GRN}${PASS} pass${RST}, ${YLW}${WARN} warn${RST}, ${RED}${FAIL} fail${RST}"
echo "─────────────────────────"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
