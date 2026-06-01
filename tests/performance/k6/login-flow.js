// k6 — login → list users → stream a skill.
//
// Phase 3 Day 30 — Agent C, mirror of `tests/performance/locustfile.py`.
// Locust gives Python-shop ergonomics; k6 gives a battle-tested binary
// with a stricter perf model and is what most platform teams reach for
// in CI/CD perf gates. Keeping both costs little and lets us
// cross-check numbers when one tool reports something surprising.
//
// Run examples (k6 must be on PATH — `brew install k6`):
//
//     # Smoke — 1 vu / 30s
//     k6 run tests/performance/k6/login-flow.js
//
//     # Ramp — 50 vu / 60s
//     K6_VUS=50 K6_DURATION=60s k6 run tests/performance/k6/login-flow.js
//
//     # Phase 5 Day 50 baseline lives in a separate scenario file once
//     # we have a stable backend; today this script just proves the rig.
//
// Backends default to the Day 28-29 dev ports. Override with env:
//
//     JAVA_BASE=http://staging.example.com:8080 \
//     PYTHON_BASE=http://staging.example.com:8000 \
//     k6 run tests/performance/k6/login-flow.js

import http from 'k6/http';
import { check, sleep } from 'k6';

const JAVA_BASE = __ENV.JAVA_BASE || 'http://127.0.0.1:8080';
const PYTHON_BASE = __ENV.PYTHON_BASE || 'http://127.0.0.1:8000';

export const options = {
  vus: parseInt(__ENV.K6_VUS || '5', 10),
  duration: __ENV.K6_DURATION || '30s',
  thresholds: {
    // Loose for a smoke run; Phase 5 will tighten these against
    // measured baselines.
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<2000'],
  },
};

const SKILL_IDS = [
  'summarize-conversation',
  'extract-entities',
  'classify-intent',
];

export default function () {
  // 1. Login — dev profile returns dev-token-{username} for any creds.
  const loginRes = http.post(
    `${JAVA_BASE}/api/v1/auth/login`,
    JSON.stringify({
      username: `k6user-${__VU}-${__ITER}`,
      password: 'dev',
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'POST /api/v1/auth/login' },
    },
  );
  check(loginRes, {
    'login 200': (r) => r.status === 200,
    'has access token': (r) => {
      try {
        const body = r.json();
        return body.accessToken || body.access_token;
      } catch (_e) {
        return false;
      }
    },
  });

  let token = '';
  try {
    const body = loginRes.json();
    token = body.accessToken || body.access_token || '';
  } catch (_e) {
    // ignore — check above already records the failure
  }

  // 2. Authenticated list — Java users.
  const usersRes = http.get(`${JAVA_BASE}/api/v1/users`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    tags: { name: 'GET /api/v1/users' },
  });
  check(usersRes, { 'users 200': (r) => r.status === 200 });

  // 3. Python skill SSE — body is the full stream; k6 reads it as text.
  const skillId = SKILL_IDS[Math.floor(Math.random() * SKILL_IDS.length)];
  const sseRes = http.post(
    `${PYTHON_BASE}/api/v1/skills/${skillId}/test/stream`,
    JSON.stringify({ input: 'k6 load ping' }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'POST /api/v1/skills/[id]/test/stream' },
    },
  );
  check(sseRes, {
    'sse 200': (r) => r.status === 200,
    'sse has data frame': (r) => typeof r.body === 'string' && r.body.includes('data:'),
  });

  sleep(Math.random() * 2 + 1);
}
