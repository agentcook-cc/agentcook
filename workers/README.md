# Cloudflare Workers — agentcook 边缘层防护

> Phase 5 backlog #11 / ADR-016 §5 / `docs/adr/draft-cloudflare-turnstile-rate-limit-design.md`

本目录有 2 个 Cloudflare Worker:

| Worker                                    | 职责                                    | 入口                    | KV            |
| ----------------------------------------- | --------------------------------------- | ----------------------- | ------------- |
| [`turnstile-verify/`](./turnstile-verify) | Turnstile token 验证(login + chat 前置) | POST `/verify`          | 无(无状态)    |
| [`rate-limit/`](./rate-limit)             | per-user 60/min + per-IP 200/min        | 任意请求(reverse proxy) | RATE_LIMIT_KV |

## 部署 SOP(作者 Day 62 真上线时操作)

### 前置(作者 Cloudflare Dashboard)

1. 创 Turnstile site `agentcook.cc` → 拿 `TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET`
2. 装 wrangler:`brew install wrangler` 或 `npm install -g wrangler@^3.60`
3. 登录:`wrangler login`(浏览器跳 Cloudflare OAuth)
4. 验证账号:`wrangler whoami` → 应返 account ID `95d7125eef7f18899c645a917bf08b0e`

### turnstile-verify deploy

```bash
cd workers/turnstile-verify
pnpm install
pnpm test                                    # 6 vitest 全 PASS
wrangler secret put TURNSTILE_SECRET --env staging
wrangler secret put TURNSTILE_SECRET --env production
pnpm deploy:staging                          # 拿 *.workers.dev URL
pnpm deploy:prod                             # 拿 *.workers.dev URL
```

实测 verify:

```bash
# 用 Cloudflare 官方 always-pass 测 token(staging only)
curl -X POST https://agentcook-turnstile-verify-staging.<account>.workers.dev/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"XXXX.DUMMY.TOKEN.XXXX"}'
# 期望 401(token 假)/ 200(若 secret 设了 always-pass test secret)
```

### rate-limit deploy

```bash
cd workers/rate-limit
pnpm install

# 创 KV namespace(staging + prod 各一)
pnpm kv:create:staging                       # 拿 namespace id → 填回 wrangler.toml
pnpm kv:create:prod                          # 拿 namespace id → 填回 wrangler.toml

# 真 deploy(域名 cascade 后)
pnpm deploy:staging
pnpm deploy:prod
```

实测 rate limit:

```bash
# staging 阈值 120/min:连发 130 req,期望最后 10 个 429
for i in $(seq 1 130); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    https://agentcook-rate-limit-staging.<account>.workers.dev/api/v1/chat/stream
done | sort | uniq -c
# 期望:120 × 200,10 × 429
```

## Worker 配额监控

Cloudflare 免费 plan:

- 每日 100,000 请求
- 每天 30s CPU 时长

目前预估(Phase 5 demo):

- turnstile-verify:每登录 / 首次 chat 触发 1 次 = 假设 100 用户 × 5 次/天 = 500 req/天
- rate-limit:每 chat / login / API 调用都过 = 假设 10K req/天

合计 ~10.5K req/天,远低于 100K 配额 ✅。真上线后看 Cloudflare Analytics 追踪。

## 与 Helm chart 的协作(降级路径)

Worker 是 Cloudflare 边缘层(第一层);Helm `templates/ingress.yaml` nginx-ingress annotations(Day 62 加)是 K8s 应用层兜底,即使 Cloudflare 全挂,K8s 内 nginx 仍能 throttle。详 `docs/devops/production-configuration.md` §5。

## 触发词清理

Worker 代码、注释、wrangler.toml 全使用中性化命名(turnstile-verify / rate-limit),无内部代号 / 真姓名。Day 63 协调员触发词扫描期望 0 命中。
