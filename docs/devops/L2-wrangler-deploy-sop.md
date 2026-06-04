# L2 — wrangler 真 deploy SOP(Cloudflare Workers / KV / Turnstile)

> 📍 **导航**:本文档是 [DEPLOYMENT.md](../../DEPLOYMENT.md) 中 **L2 Cloudflare Pages MVP** 档的 wrangler CLI 真 deploy SOP,配套 [L2-cloudflare-pages-mvp-cookbook.md](L2-cloudflare-pages-mvp-cookbook.md)(完整决策时间线 + 5 踩坑)。
>
> 📝 **关于本文档**:这是作者 2026-06-03 真执行前的逐步 SOP(原 `_internal` 笔记),包含浏览器操作 + brew/npm 兜底 + 故障复现路径。**读者执行时**:把 `<your-cloudflare-account-id>` 替换成自己 Cloudflare 账号的 Account ID(从 `dash.cloudflare.com` 右上角能看到)。
>
> ⚠️ 本文档是 SOP / 不真执行 wrangler 命令 / 真上线时按下列 4 步走

---

## 0. 真执行前置(作者 09:00-09:15)

| 项                       | 完成 | 命令 / 浏览器操作                                                                                  |
| ------------------------ | ---- | -------------------------------------------------------------------------------------------------- |
| Cloudflare 账号已登录    | ⏳   | 浏览器 dash.cloudflare.com,看 account ID = `<your-cloudflare-account-id>`                          |
| Turnstile site 已创建    | ⏳   | Dashboard → Turnstile → Add Site / Domain `agentcook.cc` / Mode `Managed` / 保存 Site Key + Secret |
| 钱包准备(无 — 免费 plan) | ✅   | Workers 免费 100K req/天 / KV 免费 1K read+write/天 / Turnstile 完全免费                           |

---

## 1. 第 1 步:brew install wrangler(09:15-09:20 / ~3 min)

```bash
# 选 ① brew(推荐 macOS / 用户已习惯)
brew install wrangler
which wrangler          # 期望 /opt/homebrew/bin/wrangler
wrangler --version      # 期望 ≥ 3.60

# 选 ② npm(若 brew 卡 stale lock — Day 51 同款故障可能复现)
npm install -g wrangler@^3.60
which wrangler          # 期望 ~/.nvm/versions/node/v20.16.0/bin/wrangler
wrangler --version
```

**故障兜底**:`brew reinstall node` 反复 stale lock(Day 51 教训),首选 npm 路径(nvm v20 LTS 已稳定)。

---

## 2. 第 2 步:wrangler login(09:20-09:25 / ~5 min,含浏览器跳转)

```bash
wrangler login
# 浏览器跳到 dash.cloudflare.com OAuth 授权页
# 作者点 "Allow"
# 跳回 terminal 显示 "Successfully logged in"

wrangler whoami
# 期望返:
#   You are logged in with an OAuth Token, associated with the email <user>@...
#   ┌────────────────────────────────────┬────────────────────────────────────┐
#   │ Account Name                       │ Account ID                         │
#   ├────────────────────────────────────┼────────────────────────────────────┤
#   │ <你的账号>                          │ <your-cloudflare-account-id>   │
#   └────────────────────────────────────┴────────────────────────────────────┘
# Account ID 必须与 workers/*/wrangler.toml 中 account_id 字段一致
```

**若 Account ID 不一致**:`grep account_id workers/*/wrangler.toml` 看与 whoami 是否对得上;不一致就 `wrangler logout` + 重 `wrangler login` 选对账号。

---

## 3. 第 3 步:secret put + KV namespace create(09:25-10:00 / ~35 min)

### 3.1 turnstile-verify

```bash
cd workers/turnstile-verify
pnpm install                                              # ~30s

# secret 注入(2 env 分别)
wrangler secret put TURNSTILE_SECRET --env staging
# Terminal 提示:Enter a secret value:
# 粘贴 staging Turnstile secret(0x4_xxx...)
# 输出:Success! Uploaded secret TURNSTILE_SECRET (binding) to env staging.

wrangler secret put TURNSTILE_SECRET --env production
# 同上,粘贴 prod secret

# 可选:staging dev bypass(测期跳过真 Cloudflare)
wrangler secret put TURNSTILE_BYPASS --env staging
# 输入:true

# verify
wrangler secret list --env staging
wrangler secret list --env production
# 期望:TURNSTILE_SECRET 在两 env 都列出
```

### 3.2 rate-limit(必须先建 KV)

```bash
cd ../rate-limit
pnpm install

# 创 2 KV namespace(staging + prod 各一,各含 production + preview 各一 = 共 4 个)
pnpm kv:create:staging
# 输出形如:
#   🌀 Creating namespace with title "agentcook-rate-limit-staging-RATE_LIMIT_KV"
#   ✨ Success! Add the following to your configuration file:
#   { binding = "RATE_LIMIT_KV", id = "abc123def456..." }
#   ❓ Also create a preview namespace? (y/n) → y
#   { binding = "RATE_LIMIT_KV", preview_id = "ghi789jkl012..." }

# 把 id + preview_id 回填 wrangler.toml `env.staging.kv_namespaces`
# 用 sed 或编辑器:
# 替换 REPLACE_WITH_STAGING_KV_ID → abc123def456...
# 替换 REPLACE_WITH_STAGING_PREVIEW_KV_ID → ghi789jkl012...

pnpm kv:create:prod
# 同样回填到 `env.production.kv_namespaces`

# 全 placeholder 已回填 verify
grep "REPLACE_WITH" wrangler.toml
# 期望 0 命中
```

---

## 4. 第 4 步:wrangler deploy + verify(10:00-10:30 / ~30 min)

### 4.1 turnstile-verify deploy

```bash
cd workers/turnstile-verify

# 4.1.1 staging
pnpm deploy:staging
# 输出形如:
#   Total Upload: 12.34 KiB / gzip: 4.56 KiB
#   Uploaded agentcook-turnstile-verify-staging (1.23 sec)
#   Published agentcook-turnstile-verify-staging (0.12 sec)
#     https://agentcook-turnstile-verify-staging.<account>.workers.dev

# 4.1.2 实测 401(假 token)
curl -s -X POST https://agentcook-turnstile-verify-staging.<account>.workers.dev/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"definitely-fake-token-doesnt-matter"}' | tee /tmp/r1.json
# 期望 JSON:{"success":false,"error":"VERIFICATION_FAILED","error_codes":[...]}
# HTTP 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://agentcook-turnstile-verify-staging.<account>.workers.dev/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"definitely-fake-token-doesnt-matter"}'
# 期望:401

# 4.1.3 prod
pnpm deploy:prod
# 同 staging 再 curl 401 verify
```

### 4.2 rate-limit deploy

```bash
cd ../rate-limit
pnpm deploy:staging
# 输出 URL:https://agentcook-rate-limit-staging.<account>.workers.dev

# 实测限速(staging 阈值 120/min,连发 130 期望最后 10 个 429)
for i in $(seq 1 130); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    https://agentcook-rate-limit-staging.<account>.workers.dev/
done | sort | uniq -c
# 期望:120 × 200 / 10 × 429
# 注意:实际 200 的 status 取决于 upstream(本 Worker 是 transparent proxy,
# 没 upstream 配真 origin 时会返 Worker 自己 fetch upstream 失败的 status 5xx)
# 若 fetch upstream 失败,Worker 仍能 throttle,所以重点是看 429 数 = 10

pnpm deploy:prod
```

### 4.3 KV id 回填 commit + push(C 配合)

```bash
cd ../..
git status
# 期望:M workers/rate-limit/wrangler.toml(2 KV id 填上)

git add workers/rate-limit/wrangler.toml
git commit -m "ops(workers): Day 68 — wrangler kv:namespace create 2 RATE_LIMIT_KV id 回填(staging + prod / C 配合作者真 deploy)"
git push origin main
```

---

## 5. 第 5 步:Cloudflare Dashboard verify(10:30-10:45 / ~15 min,浏览器)

| 项                | 路径                       | 期望                                                                          |
| ----------------- | -------------------------- | ----------------------------------------------------------------------------- |
| Worker 2 上线     | Workers & Pages → Overview | `agentcook-turnstile-verify-prod` + `agentcook-rate-limit-prod` 状态 `Active` |
| Worker analytics  | 点 Worker → Metrics        | 看 req count 已经有数(我们刚 curl 触发了)                                     |
| KV namespace 4 个 | Workers & Pages → KV       | `RATE_LIMIT_KV` × staging/preview + prod/preview = 4                          |
| Turnstile site    | Turnstile → site           | `agentcook.cc` Status Active                                                  |

---

## 6. 故障兜底速查(同 Day 66 prep §6)

| 故障                                  | 处理                                                                   |
| ------------------------------------- | ---------------------------------------------------------------------- |
| `Account ID mismatch`                 | `wrangler logout` + 重新 `wrangler login` 选对账号                     |
| `secret put` Worker 仍 missing secret | `wrangler tail --env production` 看实时 log,可能 secret 名拼错         |
| curl test 返 500 WORKER_MISCONFIGURED | `wrangler secret list --env production` 看 TURNSTILE_SECRET 是否真注入 |
| `kv:namespace create` quota exceeded  | 免费 plan 100 KV 上限,删旧的未用                                       |
| Cloudflare 边缘 timeout / 5xx         | 切回 K8s ingress 兜底(`values-prod.yaml` rateLimit.enabled=true 已开)  |

---

## 7. 完工标准(Day 68 末)

- [ ] `wrangler --version` ≥ 3.60(brew or npm 装好)
- [ ] `wrangler whoami` 显示账号 ID `<your-cloudflare-account-id>`
- [ ] 2 Worker `*.workers.dev` URL 真可访问
- [ ] turnstile-verify 假 token 返 **401**(关键 verify)
- [ ] rate-limit 130 req 中最后 10 个返 **429**
- [ ] 2 KV namespace id 回填到 wrangler.toml + git commit + push
- [ ] Cloudflare Dashboard 看 2 Worker Active
- [ ] `audit/phase6-day68-wrangler-deploy-real.md`(作者真执行后,把真 URL + curl 输出 + Cloudflare Dashboard 截图链接落档)

---

## 8. C 在 Day 68 的角色

C **不真执行**(memory `feedback-agent-physical-limits-no-gui.md` 边界):

- ❌ 不浏览器登 dash.cloudflare.com
- ❌ 不 wrangler login(OAuth 浏览器跳转)
- ❌ 不 wrangler secret put(粘真 secret 需要作者 Dashboard 拿)
- ❌ 不 wrangler deploy(真上线共享操作)

C **配合**:

- ✅ 本 SOP 文档(Day 66 prep + Day 68 SOP 双文档已就位)
- ✅ KV id 回填后帮 verify wrangler.toml + commit + push(Day 68 C 单一 commit)
- ✅ 作者真 deploy 后帮 grep `wrangler tail` log 找问题(若有)
- ✅ Day 68 末出 `audit/phase6-day68-wrangler-deploy-real.md` 把作者真执行输出固化为 audit

---

## 9. 旁路诚实

- 本文档全是 SOP / 作者真执行时数据(真 URL / 真 KV id / 真 curl 输出)需要作者粘贴回填到 audit
- wrangler 本机仍未装 → Day 68 第 1 步装 / 装好后 C 可帮 wrangler --version verify(单一无副作用命令)
- KV race condition 不原子(< 1% 误差)— design doc 已诚实,Phase 6 用 Durable Object
- 真 prod 上线后 2 Worker 占免费配额 / 用满需付费 / Day 68 末 verify Cloudflare Metrics 看 req count 增长曲线

---

**Day 68 SOP 完成签字**:Agent C · 2026-06-03 / 给作者真执行用
**配套**:`phase6-wrangler-prep.md`(Day 66 准备)+ `workers/README.md`(原 SOP 87 行)+ Day 68 真执行后 `phase6-day68-wrangler-deploy-real.md`(作者落)
