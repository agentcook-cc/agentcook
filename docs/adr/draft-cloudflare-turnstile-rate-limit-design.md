# Draft Design — Cloudflare Turnstile + Rate Limit(Phase 5 backlog #11)

**Status**:Draft / Day 60(2026-06-03)/ Buffer Day 62 实施前置
**主笔**:Agent C(DevOps + Cloudflare)
**配套**:ADR-016 §5(早记三件套 line 81-87)· ADR-018(配额 + cascade 模式参考)· `docs/devops/monitoring-alerts-sop.md`

> ⚠️ 本文档是 **设计稿**(draft-),Day 62 真实施前作者复审 + 转正成 ADR-019。本会话 **不碰真生产 / 不 helm install / 不 cf-cli 真执行**,只出实施 SOP。

---

## 1. Context

### 1.1 backlog #11 由来

ADR-016 §5(Day 49)早记三件套:Cloudflare Turnstile + Cloudflare Rate Limit + Traefik per-user rate limit。Day 51 OWASP audit A04 Insecure Design 实测确认仍 🔴(Java login 30s 434req 0 个 429 / Python 401 路径 15s 206req 0 个 429)。Phase 5 backlog #11 转入 Buffer Day 62 解。

### 1.2 真栈现状(grep 实测,memory `feedback-fact-check-before-finalize`)

| 项               | 真路径                                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Java login 端点  | `agentcook-java/agentcook-api/.../AuthController.java:40` `@PostMapping("/login")` → `/api/v1/auth/login`              |
| Python chat 端点 | `agentcook/src/agentcook_app/routers/chat.py:27` `APIRouter(prefix="/api/v1/chat")` → `POST /api/v1/chat/stream` (SSE) |
| Cloudflare 账号  | account ID `95d7125eef7f18899c645a917bf08b0e`(release-checklist line 10)                                               |
| 当前 rate limit  | 0(Day 51 实测确认)                                                                                                     |

---

## 2. Decision

### 2.1 选型:Cloudflare Turnstile(三选一)

| 方案                     | 价格                   | 隐私                              | UX                      | SEO        | bot 检测                                 | 推荐        |
| ------------------------ | ---------------------- | --------------------------------- | ----------------------- | ---------- | ---------------------------------------- | ----------- |
| **Cloudflare Turnstile** | **免费(无配额限)**     | privacy-first(无 cookie 跨站追踪) | 多数情况隐形 / 偶发挑战 | ✅ 不影响  | ML + 设备指纹 + Cloudflare global signal | ✅ **推荐** |
| Google reCAPTCHA v3      | 1M req/月免费,超出付费 | 全 Google 跨站追踪 / 隐私槽点     | 隐形评分制              | 🟡 GA 关联 | 强(Google 数据)                          | ❌          |
| hCaptcha                 | 1M req/月免费,超出付费 | privacy 较好                      | 显式挑战 / UX 略重      | ✅         | 强                                       | 🟡 备选     |

**推荐 Turnstile**,3 个理由:① **完全免费无配额限制**(Phase 5 demo 阶段 LLM 烧爆是首要焦虑,验证码免费契合 ADR-016 §核心理念)② **privacy-first 不种 cookie 跨站追踪**(对国内合规更稳)③ **本项目已用 Cloudflare Pages + DNS,接入零额外账号成本**(release-checklist Step 4-5 印证)

### 2.2 接入方案

#### 2.2.1 前端 widget 接入(B 领地 / cascade 第 3 步)

```
agentcook-admin/src/pages/LoginPage.tsx
agentcook-app/src/pages/LoginPage.tsx
agentcook-app/src/components/ChatInput.tsx (Day 56 B 已加配额显示,加 Turnstile 同位置)
```

每处加 Turnstile 组件:

```tsx
// 通用 hook(B Day 64 新建 agentcook-app/src/hooks/useTurnstile.ts)
import { Turnstile } from "@marsidev/react-turnstile";

<Turnstile
  siteKey={import.meta.env.VITE_TURNSTILE_SITE_KEY}
  onSuccess={(token) => setTurnstileToken(token)}
  onError={() => setTurnstileToken(null)}
  options={{ theme: "auto", size: "normal" }}
/>;
```

**触发时机**:

- login:用户点 "登录" 前 widget 必须返 token,token 随 login body 发后端
- chat:**只在前 N 次未验证时显示**(N=3,与 ADR-018 配额 v1=2 次/账号互补 — 第一次 chat 强制验证,后续凭 JWT scope `verified`),避免每次输入都打扰

#### 2.2.2 后端验证(D Java + A Python / cascade 第 1-2 步)

**Java login(D Day 62 早晨):**

```java
// agentcook-api/src/main/java/.../auth/TurnstileVerifier.java(新建)
@Component
public class TurnstileVerifier {
    @Value("${agentcook.turnstile.secret:}")  // env 注入,dev 可空
    private String secret;

    public boolean verify(String token, String remoteIp) {
        if (secret.isEmpty()) return true;  // dev profile 跳过
        // POST https://challenges.cloudflare.com/turnstile/v0/siteverify
        // body: secret=$SECRET&response=$TOKEN&remoteip=$IP
        // 期望 response.success == true
    }
}

// AuthController.login() 入口先验:
if (!turnstile.verify(req.turnstileToken(), req.remoteIp())) {
    throw new ApiException("AUTH_TURNSTILE_FAILED", 401);
}
```

**Python chat(A Day 62 中午):**

```python
# agentcook_app/middleware/turnstile.py(新建,与 quota.py Day 56 同目录)
async def verify_turnstile(request: Request) -> None:
    if not settings.turnstile_secret:
        return  # dev 跳过
    token = request.headers.get("X-Turnstile-Token")
    if not token:
        raise HTTPException(401, "AUTH_TURNSTILE_MISSING")
    # POST cloudflare siteverify,fail → 401
```

应用到 `routers/chat.py:144` `POST /chat/stream` 前置 dependency。

#### 2.2.3 Cloudflare Worker 验证(可选 / 边缘层 / Phase 5 buffer 后)

不强制走 Worker — Worker 加一层延迟(~50ms)且 Java/Python 已直接验。**首发版选直接验**;真上线后流量大若希望减后端压力再加 Worker 提前 reject 无 token 请求。Worker 配额免费 10万 req/天,够。

### 2.3 Rate Limit 方案

#### 2.3.1 双层防御

| 层               | 工具                               | 阈值                                              | 实施位                                                |
| ---------------- | ---------------------------------- | ------------------------------------------------- | ----------------------------------------------------- |
| **边缘层(优先)** | Cloudflare Rate Limit Rule         | 整站 200 req/IP/min                               | Cloudflare Dashboard → Security → WAF → Rate Limiting |
| **应用层**       | Traefik / nginx-ingress middleware | per-user 60 req/min(chat)/ per-IP 200 req/min(全) | `agentcook-swarm/gateway/dynamic/middlewares.yml`     |
| **业务层**       | ADR-018 配额机制                   | per-account 2 次免费 / 自动降级 glm-4-flash       | A Day 56 quota middleware 已落                        |

**为什么双层**:Cloudflare 边缘层防 DDoS / 大流量(整站维度 / 不区分 user);Traefik / nginx 应用层防 per-user 滥用(认证后维度);ADR-018 业务层防 LLM cost 烧爆(per-account)。三层职责互补不重复。

#### 2.3.2 chat 端点细化阈值(对照 Day 50 baseline)

Day 50 100u 真栈 baseline:RPS 27.73 / 单用户极限测假设 1 req/3s = ~20 req/min。设阈值留 3× headroom:

```yaml
# agentcook-swarm/gateway/dynamic/middlewares.yml(Day 62 C 新增 / Traefik 自带 ratelimit)
http:
  middlewares:
    chat-ratelimit-per-user:
      rateLimit:
        average: 60 # 60 req/min
        period: 1m
        burst: 20 # 短暂突发可超
        sourceCriterion:
          ipStrategy:
            depth: 1 # 取 X-Forwarded-For 第 1 层(Cloudflare 真 IP)
    chat-ratelimit-per-ip:
      rateLimit:
        average: 200
        period: 1m
        burst: 50
```

**误伤校准**:阈值高于 Day 50 单用户实测 3×,正常用户 ~20 req/min 远低 60 阈值;只对 60+ 才 throttle(机器人 / 滥用)。

#### 2.3.3 K8s nginx-ingress 备选(若不用 Traefik)

```yaml
# Ingress annotations(Day 62 备选)
nginx.ingress.kubernetes.io/limit-rpm: "60"
nginx.ingress.kubernetes.io/limit-rps: "5"
nginx.ingress.kubernetes.io/limit-connections: "10"
```

**推荐主路径用 Traefik**(Phase 4 Day 38-40 已选 / staging compose 已含),备选 nginx 留 prod 切换时复用。

---

## 3. 实施 Cascade(参考 ADR-018 D → A → B 模式)

```
Buffer Day 62 早晨 09:00-11:00:
  D(Java backend / 优先环节):
    1. 新建 agentcook-api/.../auth/TurnstileVerifier.java(80 行)
    2. AuthController.login() 入口加 verify(JWT 颁发前先过 Turnstile)
    3. application.yml + application-prod.yml 加 agentcook.turnstile.{siteKey,secret}
    4. Helm values.yaml + values-prod.yaml 加 secret.turnstileSecret 字段(C 配合一行)
    5. 测试:TurnstileVerifierTest(mock siteverify HTTP 200/400)+ AuthControllerIT(token 缺失 → 401)
    6. mvn test 不退 / commit `feat(auth): D Day 62 Cloudflare Turnstile login 验证(backlog #11)`

Buffer Day 62 中午 11:00-13:00:
  A(Python middleware / 中间环节):
    1. 新建 agentcook/src/agentcook_app/middleware/turnstile.py(~80 行,与 quota.py 同目录)
    2. routers/chat.py:144 stream 端点加 dependency(verify 先于 quota check)
    3. tests/test_turnstile_middleware.py(5 场景:dev 跳 / 缺 token 401 / 假 token 401 / 真 token 200 / network fail 503)
    4. pytest 不退 / commit `feat(chat): A Day 62 Turnstile 验证 + chat dependency(backlog #11)`

Buffer Day 62 下午 13:00-16:00:
  B(前端 widget / 最后环节):
    1. agentcook-admin/src/pages/LoginPage.tsx 加 <Turnstile> 组件
    2. agentcook-app/src/pages/LoginPage.tsx 同款
    3. agentcook-app/src/hooks/useTurnstile.ts 新建(共用 hook)
    4. agentcook-app/src/components/ChatInput.tsx 加 Turnstile(只前 N=3 次)
    5. .env.local + .env.production 加 VITE_TURNSTILE_SITE_KEY
    6. e2e 1 场景(token 流转端到端 PASS)
    7. pnpm test 不退 / commit `feat(auth): B Day 62 Turnstile widget 三处接入(backlog #11)`

Buffer Day 62 下午 16:00-17:00:
  C(配合环节 / Cloudflare + Traefik 配置):
    1. 作者 Cloudflare Dashboard 创建 Turnstile site(产生 siteKey + secret)
    2. C 把 siteKey 注入 GitHub Actions secrets(VITE_TURNSTILE_SITE_KEY)
    3. C 把 secret 注入 K8s Secret(staging + prod via SealedSecret / ExternalSecret)
    4. C agentcook-swarm/gateway/dynamic/middlewares.yml 加 chat-ratelimit-per-user / per-ip 2 段
    5. C Cloudflare Dashboard → Security → WAF → Rate Limit 配整站 200 req/IP/min(作者授权后真配)
    6. C commit `ops(security): C Day 62 Turnstile secret + Traefik rate limit middleware(backlog #11)`
```

**前置依赖**(Day 62 09:00 前作者操作):

- 登 Cloudflare Dashboard → Turnstile → 创 site `agentcook.cc` → 拿 siteKey + secret
- 拿到后给 C 注入 secrets

---

## 4. 监控:Grafana dashboard 加 4 panel

新增 Grafana dashboard `agentcook-swarm/grafana/dashboards/security-rate-limit.json`(Day 62 末 C 落):

| panel                      | promql                                                                                | 用途                                 |
| -------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------ |
| Turnstile 验证失败率       | `rate(turnstile_verify_total{outcome="fail"}[5m]) / rate(turnstile_verify_total[5m])` | bot 攻击信号 / 阈值 > 30% 触发 alert |
| Rate Limit hit count       | `sum(rate(traefik_service_requests_total{code="429"}[5m])) by (service)`              | 哪个 endpoint 被刷最多               |
| Blocked IP top 10          | `topk(10, sum by (client_ip) (rate(traefik_service_requests_total{code="429"}[1h])))` | 反黑名单参考                         |
| Cloudflare WAF block(可选) | Cloudflare Analytics API → Prometheus exporter / 或 Cloudflare GraphQL                | 边缘层拦截量                         |

**配套 PrometheusRule**(`prometheusrule.yaml` Day 53 加 group `agentcook.security`):

```yaml
- alert: AgentcookTurnstileFailRateHigh
  expr: rate(turnstile_verify_total{outcome="fail"}[5m]) / rate(turnstile_verify_total[5m]) > 0.3
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Turnstile 验证失败率 > 30% / 可能机器人攻击"

- alert: AgentcookRateLimitHitSpike
  expr: sum(rate(traefik_service_requests_total{code="429"}[5m])) > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Rate Limit 触发 > 10 次/min / 可能滥用"
```

监控 SOP 加到 `monitoring-alerts-sop.md` § 4 表(Day 62 末与 dashboard commit 同步)。

---

## 5. 风险评估

| #      | 风险                                                                            | 严重度 | 缓解                                                                                                                                                                                              |
| ------ | ------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R1** | **Turnstile 阻塞登录**(Cloudflare 服务故障 / 国内 \*.cloudflare.com DNS 污染)   | 🔴 高  | ① 后端 secret 留空时跳过验证(dev profile)② 监控 Cloudflare status page,故障期手动配置回退环境变量 `TURNSTILE_BYPASS=true` ③ 国内用户备选 hCaptcha(预留接口)                                       |
| **R2** | **Rate Limit 误伤真实用户**(60 req/min 太低 / 共享 IP 办公室)                   | 🟡 中  | ① 阈值以 Day 50 baseline 3× headroom 设(20 → 60)② 监控 429 突增 alert / 收到立刻校准 ③ per-user(JWT sub)优先于 per-IP — 登录用户不受 IP 共享影响                                                  |
| **R3** | **Cloudflare Worker 配额超限**(若启用 Worker / 免费 10 万 req/天)               | 🟢 低  | ① 首发不启 Worker / 只用 Turnstile + 后端直接验 ② 流量超 10 万/天再开 Worker(届时已有付费空间)③ Cloudflare 配额超会 throttle 不会 charge                                                          |
| **R4** | **siteKey 泄露**(前端 .env.production 暴露)                                     | 🟢 低  | siteKey 设计就是公开(嵌入 widget),secret 才必须保密。secret 走 K8s Secret + ExternalSecret(`production-configuration.md` §5 已规定)                                                               |
| **R5** | **Turnstile 触发率太高 / UX 槽**(用户每次登录都看到挑战)                        | 🟡 中  | ① 用 Turnstile invisible 模式(默认),只在风险信号高时挑战 ② 监控"挑战展示率"panel(Cloudflare Analytics)③ 阈值 > 20% 触发就调 Turnstile aggressiveness                                              |
| **R6** | **chat 端点配额 + Rate Limit 双重触发用户混淆**(用户分不清是被限速还是配额耗尽) | 🟡 中  | ① 后端错误码区分:`RATE_LIMITED` vs `QUOTA_EXHAUSTED` ② B 前端 ChatInput 显示明确提示("您已触发限速,请 1 分钟后重试" / "您的免费配额已用尽,自动降级到 glm-4-flash")③ 协调 ADR-018 配额提示文案统一 |
| **R7** | **Cloudflare 账号绑定单点风险**(账号挂 / 误删 site key)                         | 🟢 低  | ① siteKey + secret 备份到 1Password / Bitwarden ② Cloudflare 账号开 2FA(release-checklist v4.1 §4 已说)                                                                                           |

---

## 6. 测试 + 验收

### 6.1 单元测试(D + A 各自)

- D `TurnstileVerifierTest`:5 场景(空 secret 跳过 / 真 token 200 / 假 token 401 / Cloudflare 504 → 503 / token 过期 401)
- A `test_turnstile_middleware.py`:5 场景同款

### 6.2 集成测试(B)

- e2e 1 场景:模拟 Turnstile widget 返 dummy token → 后端 mock siteverify 返 success → login 200 / chat 200 流转端到端 PASS

### 6.3 验收 criteria(Day 62 末作者拍板)

- [ ] 真 Cloudflare site 创建 + siteKey + secret 拿到
- [ ] 三处前端 widget 显示(2 login + 1 chat)
- [ ] 后端 401 响应 `AUTH_TURNSTILE_FAILED`
- [ ] Traefik rate limit 60/200 真触发 429(curl 极速 ≥ 60 次)
- [ ] Cloudflare WAF 整站 200/IP/min 真生效(作者 Dashboard 配)
- [ ] Grafana 4 panel + 2 PrometheusRule alert 渲染
- [ ] 真 chat 流程不破坏(配额 + Turnstile + Rate Limit 三层不冲突)

---

## 7. 转正路径(Day 62 实施完 → ADR-019)

本 draft → Day 62 实施完 → 改 commit `docs(adr): ADR-019 Cloudflare Turnstile + Rate Limit(实施版,from draft)` → 删 `draft-` 前缀 → 更新 ADR-016 §5 / ADR-018 §parking-lot 引用 ADR-019。

**与 ADR-018 关系**:ADR-018 是业务层配额(per-account 2 次免费 / 降级 glm-4-flash);ADR-019 是边缘 + 应用层防滥用(Turnstile bot 检测 + per-user/IP rate limit)。**两 ADR 互补不重复** — ADR-018 防 LLM cost 烧爆,ADR-019 防机器人 / 大流量 DDoS / API 滥用。

---

## 8. 旁路诚实交代

- 本 draft **完全不碰真生产**(不 helm install / 不 cf-cli 真执行 / 不创真 Cloudflare site)— 严守 brief 边界
- 真 cf siteverify HTTP 调用本机未实测(需要真 secret + Cloudflare 账号操作 / Day 62 真实施时 D + A 测试 mock + 集成测试 PASS)
- Turnstile 国内可用性凭"Cloudflare CDN 国内多数地区可达"假设;若真上线后用户反馈卡 Turnstile,启 R1 缓解 ② 手动 bypass 环境变量
- chat 端点 Turnstile "前 N=3 次"策略是 UX 经验值 / 没真用户数据支撑 / 真上线后看 Turnstile 触发率调
- Rate Limit 60/200 阈值基于 Day 50 100u baseline 3× headroom / 真业务量到 1000+ 用户后必须重校准

---

**Draft 完成签字**:Agent C · 2026-06-03 · Day 60 末(Buffer 前置)
**配套**:ADR-016 §5 / ADR-018 cascade 模式 / `production-configuration.md` §5 / `monitoring-alerts-sop.md` §4
