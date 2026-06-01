# Deploying docs-site to Cloudflare Pages

The docs site is a static VitePress build. We deploy to Cloudflare Pages
because it gives free global CDN + automatic SSL + per-PR preview
deployments.

## Build settings

| Setting | Value |
|---------|-------|
| Framework preset | None (custom) |
| Build command | `pnpm install --frozen-lockfile && pnpm --filter @agentcook-cc/docs-site docs:build` |
| Build output directory | `docs-site/.vitepress/dist` |
| Root directory | `/` (monorepo root, leave as-is) |
| Node version | `20` (set via `NODE_VERSION` env var) |
| Environment variables | `NODE_VERSION=20`, `CI=true` |

Cloudflare's UI lets you paste the build command directly. The output
path is relative to the repo root.

## Custom domain

1. In Cloudflare Pages → **Custom domains** → **Set up a custom domain**
2. Enter `agentcook.cc`
3. Cloudflare creates the CNAME automatically when DNS is already in
   Cloudflare. If DNS is elsewhere, add `CNAME agentcook.cc →
   PROJECT.pages.dev` at your registrar.

SSL is provisioned automatically (Universal SSL, typically ready in <
5 minutes).

## Local preview

```bash
pnpm --filter @agentcook-cc/docs-site docs:dev     # dev server, hot reload
pnpm --filter @agentcook-cc/docs-site docs:build   # production build
pnpm --filter @agentcook-cc/docs-site docs:preview # serve the production build
```

The build output is `docs-site/.vitepress/dist/` — the exact tree
Cloudflare uploads.

## Per-PR previews

Cloudflare Pages auto-creates a preview deployment for every PR. The URL
shows up as a comment on the PR. No extra config needed beyond connecting
the GitHub repo to the Cloudflare project.

## Cache + 404 behaviour

VitePress emits clean URLs (`/guide/installation` instead of
`/guide/installation.html`) and a `404.html` fallback. Cloudflare's
default static-site routing honours both — no `_redirects` file needed.

## Rollback

In Cloudflare Pages → **Deployments**, pick a previous successful
deployment and click **Rollback to this deployment**. The promotion is
near-instant (CDN-only switch, no rebuild).

## Where to look when it breaks

- **Build fails**: Cloudflare's build log is at *Deployments → click the
  failing build → Build log*. Usually a pnpm lockfile mismatch or a
  Node version skew.
- **404 on a known page**: VitePress only emits a route if there's a
  corresponding `.md` file under `docs-site/`. Check that the file
  exists and that its path matches the sidebar config in
  `.vitepress/config.ts`.
- **Wrong content showing**: Cloudflare aggressively caches HTML.
  Trigger a redeploy or purge the cache from the Cloudflare dashboard.
