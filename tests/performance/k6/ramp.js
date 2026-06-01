// k6 — multi-stage ramp scenario.
//
// Phase 3 Day 31 — Agent C. Companion to `login-flow.js`: same three
// flows, structured as a ramp-up/hold/ramp-down so we observe how the
// stack absorbs gradient load rather than a flat-line burst.
//
// Stages (default):
//   - 0..30s    ramp 0 → 100 VUs
//   - 30..90s   hold 100 VUs
//   - 90..120s  ramp 100 → 0 VUs
//
// Override via env when characterising a different stack:
//
//     RAMP_PEAK=200 RAMP_HOLD=120s RAMP_RAMP_UP=60s RAMP_RAMP_DOWN=60s \
//       k6 run tests/performance/k6/ramp.js
//
// Thresholds are deliberately loose (this is the first ramp baseline —
// Phase 5 Day 50 tightens them once we have measured numbers from a
// stable backend). The goal today is to confirm the rig holds, not to
// gate on perf SLOs.

import http from 'k6/http';
import { check, sleep } from 'k6';

const JAVA_BASE = __ENV.JAVA_BASE || 'http://127.0.0.1:8080';
const PYTHON_BASE = __ENV.PYTHON_BASE || 'http://127.0.0.1:8000';

const PEAK_VUS = parseInt(__ENV.RAMP_PEAK || '100', 10);
const RAMP_UP = __ENV.RAMP_RAMP_UP || '30s';
const HOLD = __ENV.RAMP_HOLD || '60s';
const RAMP_DOWN = __ENV.RAMP_RAMP_DOWN || '30s';

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: RAMP_UP, target: PEAK_VUS },
        { duration: HOLD, target: PEAK_VUS },
        { duration: RAMP_DOWN, target: 0 },
      ],
      gracefulRampDown: '15s',
    },
  },
  thresholds: {
    // Loose Phase-3 baseline; tighten in Phase 5 Day 50 once we have
    // measured numbers from a stable backend.
    http_req_failed: ['rate<0.10'],
    http_req_duration: ['p(95)<3000', 'p(99)<7000'],
    // Per-endpoint gates — surface which surface degrades first.
    'http_req_duration{name:POST /api/v1/auth/login}': ['p(95)<2000'],
    'http_req_duration{name:GET /api/v1/skills}': ['p(95)<2000'],
  },
};

const SKILL_IDS = [
  'summarize-conversation',
  'extract-entities',
  'classify-intent',
];

export default function () {
  // 1. Login — dev profile dummy token; Day 31 onwards Spring Security
  // accepts these in dev mode (per D's Day 31 Security OAuth2 plan).
  const loginRes = http.post(
    `${JAVA_BASE}/api/v1/auth/login`,
    JSON.stringify({
      username: `ramp-${__VU}-${__ITER}`,
      password: 'dev',
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'POST /api/v1/auth/login' },
    },
  );
  check(loginRes, { 'login 200': (r) => r.status === 200 });

  let token = '';
  try {
    const body = loginRes.json();
    token = body.accessToken || body.access_token || '';
  } catch (_e) {
    // tracked via the check above
  }

  // 2. Java users list under load — proves the SecurityFilterChain hot path.
  const usersRes = http.get(`${JAVA_BASE}/api/v1/users`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    tags: { name: 'GET /api/v1/users' },
  });
  check(usersRes, { 'users 200 or 405': (r) => r.status === 200 || r.status === 405 });
  // 405 tolerated until D's Day 31 rebuild lands; check is informational.

  // 3. Python skill list — pure read path on FastAPI.
  const skillsRes = http.get(`${PYTHON_BASE}/api/v1/skills`, {
    tags: { name: 'GET /api/v1/skills' },
  });
  check(skillsRes, { 'skills 200': (r) => r.status === 200 });

  // 4. Python SSE stream — long-tail latency contributor. Only every
  // 4th iteration to avoid flooding (10×500ms × 100 VUs is a lot of
  // concurrent streams; we throttle here rather than at the scenario level).
  if (__ITER % 4 === 0) {
    const skillId = SKILL_IDS[Math.floor(Math.random() * SKILL_IDS.length)];
    const sseRes = http.post(
      `${PYTHON_BASE}/api/v1/skills/${skillId}/test/stream`,
      JSON.stringify({ input: 'ramp ping' }),
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'POST /api/v1/skills/[id]/test/stream' },
      },
    );
    check(sseRes, {
      'sse 200': (r) => r.status === 200,
      'sse has data frame': (r) => typeof r.body === 'string' && r.body.includes('data:'),
    });
  }

  sleep(Math.random() * 2 + 1);
}
