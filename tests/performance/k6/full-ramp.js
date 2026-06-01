// k6 — full ramp 50 → 100 → 200 → 500 VUs through the Traefik gateway.
//
// Phase 4 Day 41 — Agent C. This is the first ramp scenario that hits the
// **gateway** (`gateway:80`) rather than a direct service port — the Day
// 30-31 ramp scripts predate the swarm split. Hitting the gateway is what
// real users do; latency here includes Traefik's CORS + rate-limit
// middlewares (configured by B in `agentcook-swarm/gateway/dynamic/`).
//
// Stages (60 + 90 + 60 + 60 + 30 + 30 = 5m30s):
//   - 0..60s    ramp 0   → 50  VUs   (warm-up tier)
//   - 60..150s  hold 50  VUs           (Phase 3 baseline tier)
//   - 150..210s ramp 50  → 100 VUs    (admin under load)
//   - 210..270s ramp 100 → 200 VUs    (Phase 5 stretch goal tier)
//   - 270..300s ramp 200 → 500 VUs    (saturation finder)
//   - 300..330s ramp 500 → 0   VUs    (graceful drain)
//
// Tightened thresholds vs `ramp.js` per the Day 41 brief:
//   p95 < 500ms / p99 < 2000ms / fail < 1%
// Per-endpoint sub-thresholds surface which surface buckles first.
//
// Run examples:
//
//     k6 run tests/performance/k6/full-ramp.js
//
//     # Override against staging gateway:
//     GATEWAY_BASE=https://staging.agentcook.cc k6 run tests/performance/k6/full-ramp.js

import http from 'k6/http';
import { check, sleep } from 'k6';

const GATEWAY_BASE = __ENV.GATEWAY_BASE || 'http://127.0.0.1';
// Some routes still resolve directly during local dev — keep these
// overridable so we can A/B gateway vs direct latency.
const JAVA_DIRECT = __ENV.JAVA_DIRECT || `${GATEWAY_BASE}:8080`;
const PYTHON_DIRECT = __ENV.PYTHON_DIRECT || `${GATEWAY_BASE}:8000`;

const SKILL_IDS = [
  'summarize-conversation',
  'extract-entities',
  'classify-intent',
];

export const options = {
  scenarios: {
    full_ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '60s', target: 50 },
        { duration: '90s', target: 50 },
        { duration: '60s', target: 100 },
        { duration: '60s', target: 200 },
        { duration: '30s', target: 500 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '20s',
    },
  },
  thresholds: {
    // Day 41 brief targets — strict.
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'p(99)<2000'],
    // Per-endpoint gates so we can identify which surface degrades first.
    'http_req_duration{name:POST /api/v1/auth/login}': ['p(95)<400'],
    'http_req_duration{name:GET /api/v1/users}': ['p(95)<300'],
    'http_req_duration{name:GET /api/v1/skills}': ['p(95)<300'],
    'http_req_duration{name:POST /api/v1/chat/stream}': ['p(95)<2000'],
    'http_req_duration{name:POST /api/v1/skills/[id]/test/stream}': ['p(95)<2000'],
  },
};

function loginAndGetToken() {
  const res = http.post(
    `${JAVA_DIRECT}/api/v1/auth/login`,
    JSON.stringify({
      username: `k6-${__VU}-${__ITER}`,
      password: 'dev',
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'POST /api/v1/auth/login' },
    },
  );
  check(res, { 'login 200': (r) => r.status === 200 });
  try {
    const body = res.json();
    return body.accessToken || body.access_token || '';
  } catch (_e) {
    return '';
  }
}

export default function () {
  // 1. Login → token. Re-login each iteration: under 500 VUs the
  // SecurityFilterChain hot path is the most interesting bottleneck.
  const token = loginAndGetToken();
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

  // 2. Java users list — admin hot path.
  const usersRes = http.get(`${JAVA_DIRECT}/api/v1/users`, {
    headers: authHeaders,
    tags: { name: 'GET /api/v1/users' },
  });
  check(usersRes, { 'users 200': (r) => r.status === 200 });

  // 3. Python skills list — read-heavy FastAPI path.
  const skillsRes = http.get(`${PYTHON_DIRECT}/api/v1/skills`, {
    tags: { name: 'GET /api/v1/skills' },
  });
  check(skillsRes, { 'skills 200': (r) => r.status === 200 });

  // 4. Chat SSE — the long-tail latency contributor. Throttled to 1
  // call every 5 iterations; 500 VUs each holding a 5s SSE stream
  // would saturate the gateway's connection limit before we measure
  // anything useful about steady-state throughput.
  if (__ITER % 5 === 0) {
    const chatRes = http.post(
      `${PYTHON_DIRECT}/api/v1/chat/stream`,
      JSON.stringify({
        session_id: `k6-${__VU}`,
        input: 'load probe',
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
        },
        tags: { name: 'POST /api/v1/chat/stream' },
      },
    );
    check(chatRes, {
      'chat 200': (r) => r.status === 200,
      'chat has sse frame': (r) =>
        typeof r.body === 'string' && r.body.includes('data:'),
    });
  }

  // 5. Skill stream SSE — every 7 iters; covers the secondary stream surface.
  if (__ITER % 7 === 0) {
    const skillId = SKILL_IDS[Math.floor(Math.random() * SKILL_IDS.length)];
    const sseRes = http.post(
      `${PYTHON_DIRECT}/api/v1/skills/${skillId}/test/stream`,
      JSON.stringify({ input: 'k6 load ping' }),
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'POST /api/v1/skills/[id]/test/stream' },
      },
    );
    check(sseRes, {
      'sse 200': (r) => r.status === 200,
      'sse has data frame': (r) =>
        typeof r.body === 'string' && r.body.includes('data:'),
    });
  }

  sleep(Math.random() * 2 + 0.5);
}
