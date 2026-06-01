# Frontend Observability

Web Vitals client-side instrumentation for `agentcook-app` (React) and
`agentcook-admin` (Vue 3). Same module is duplicated under both surfaces;
extract to a shared package only after Day 24+ once the OTel collector path is
stable and we know the surface tag is the only divergence.

## Metrics collected

We use the [`web-vitals`](https://github.com/GoogleChrome/web-vitals) v5 SDK
(< 5 KB gzipped). v5 dropped the deprecated FID metric in favour of INP, which
is a strictly better measure of interaction latency.

| Metric | What it measures | Good threshold |
|--------|------------------|---------------|
| **LCP** | Largest Contentful Paint — main content render time | < 2.5 s |
| **CLS** | Cumulative Layout Shift — visual stability | < 0.1 |
| **INP** | Interaction to Next Paint — input responsiveness (replaces FID) | < 200 ms |
| **TTFB** | Time To First Byte — server + network warmup | < 800 ms |
| **FCP** | First Contentful Paint — first pixel of any text/image | < 1.8 s |

Each sample is tagged with `surface: "app" | "admin"` so the future collector
can split dashboards per surface without re-deriving from URL or User-Agent.

## Day 23 status: console.log only

`installWebVitals({ surface })` defaults to printing each sample to
`console.log` with the schema below. Day 24+ work (waiting on Agent A's OTel
collector path from the backend instrumentation) will swap the reporter for
an HTTP/OTLP exporter — the API is already injection-ready:

```ts
installWebVitals({
  surface: "app",
  reporter: (sample) => {
    // POST sample to /v1/observability/web-vitals or push to OTel JS SDK
  },
});
```

## Sample console output

```text
[web-vitals] {
  surface: "app",
  name: "LCP",
  value: 1842.5,
  rating: "good",
  delta: 1842.5,
  id: "v5-1748534921012-7320481",
  navigationType: "navigate"
}
```

## Why we did NOT wire to OTel today

Per Day 23 brief: A is still landing the OTel SDK on the Python side. Pushing
client-side metrics now means either (a) inventing a custom `/web-vitals`
endpoint we'll throw away, or (b) shipping the OTel JS SDK twice (~30 KB
extra) before the collector route is stable. Decision deferred to Day 24+
when Agent A confirms the collector endpoint and auth model.

## Verification

```bash
pnpm --filter @agentcook-cc/app dev    # localhost:5173
pnpm --filter @agentcook-cc/admin dev  # localhost:5174
```

Open browser → DevTools console → interact with the page (click, scroll, type)
→ entries tagged `[web-vitals]` should appear within ~1 second of meaningful
events. Note CLS / INP / LCP only fire on `visibilitychange` or after first
interaction by design — these are not synchronous-on-load metrics.

## Files

- `web-vitals.ts` — installer + default console reporter, identical in `app`
  and `admin` surfaces (intentional duplication; extract to shared package
  Day 24+ once API stabilises).
- `agentcook-app/src/main.tsx` — calls `installWebVitals({ surface: "app" })`
  after `createRoot.render`.
- `agentcook-admin/src/main.ts` — calls `installWebVitals({ surface: "admin" })`
  after `app.mount`.

## Roadmap

- **Day 24+** — point `reporter` at OTel collector once A confirms ingest path
- **Phase 4 Day 38–47** — when admin/app go to staging, gate console reporter
  behind `import.meta.env.DEV` so prod only ships the collector path
- **Phase 5 Day 50** — Lighthouse-driven perf budget enforcement; alert if
  LCP > 2.5s or CLS > 0.1 in three consecutive sessions
