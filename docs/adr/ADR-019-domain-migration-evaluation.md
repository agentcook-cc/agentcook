# ADR-019: 主域名迁移评估 (`<CURRENT_DOMAIN>` → `<NEW_DOMAIN>`)

## Status

**Accepted — defer to Phase 6 第 1 周（Day 70-72）** (2026-06-07,Buffer Day 64 D 主战评估,基于 Day 60 末 `draft-laoa-dev-cascade-impact.md` 升级)

## Context

Phase 4.5 真上线推迟到首发前（作者 2026-06-01 GO）。Buffer Day 64-65 D 与协调员主战 = 评估"购入 `<NEW_DOMAIN>` 替换工程内部 `<CURRENT_DOMAIN>` + Cloudflare Pages 默认域 (`<CURRENT_DOCS_DOMAIN>`)"的可行性、cascade 改动范围、风险与上线时机。

本 ADR 是 **impact analysis + 时机决策**，**不触发真改动**（不动 `.env` / 不跑 `cf-cli` / 不 `helm upgrade`）；真改造由 Phase 6 第 1 周按本 ADR §"Cascade 4 步"执行。

工程当前外露的域名标识有三种：

1. `<CURRENT_DOMAIN>`（工程默认主域 + `staging.<…>` + `api.<…>` 子域）
2. `<CURRENT_DOCS_DOMAIN>`（Cloudflare Pages 默认提供的 docs 镜像域）
3. `<NEW_DOMAIN>`（本 cascade 的目标，未购入）

目标：把 1、2 替换为 `<NEW_DOMAIN>` 体系，保留 Cloudflare Pages 默认域 7 天作为 fallback；首发期间继续用 `<CURRENT_DOMAIN>`（已 stable 30+ 天），cascade 改造留 Phase 6 第 1 周窗口期。

---

## Source（grep 实测 stdout，防协调员脑补 / cookbook 坑 23 子项）

```bash
cd /Users/yvan/workspace/accio-work/agentcook-cc && \
  grep -rn "agentcook\.cc\|agentcook-docs\.pages\.dev\|agentcook\.pages\.dev" . \
       --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=target --exclude-dir=__pycache__ \
       2>/dev/null | wc -l
# → 69 行命中 / 26 个文件
```

Top 命中文件实测：

```
10  docs/devops/production-configuration.md
 7  agentcook-design-tokens/docs/frontend-conventions.md
 4  docs/devops/k8s-operations-manual.md
 3  agentcook-{app,admin}/.env.{staging,production}    (4 文件 × 3 行 = 12)
 3  docs/architecture/03-k8s-deployment.md
 2  deploy/helm/agentcook/values.yaml
 2  docs-site/.vitepress/config.ts
 2  tests/performance/PERFORMANCE-REPORT.md
 2  docs/api/DEPRECATION-POLICY.md
 2  docs/adr/ADR-006-blue-green-deployment.md
 2  docs-site/DEPLOY.md
 2  agentcook-app/README.md
 2  agentcook-java/agentcook-api/.../OpenApiConfig.java
 1  其余 13 文件各 1 行
```

---

## Decision

### 1. 分类清单（按改动复杂度）

| 类                           | 文件数 |   行数 | 处理方式                   |
| ---------------------------- | -----: | -----: | -------------------------- |
| 🔴 代码硬编码（真 refactor） |      2 |      3 | 抽 `@Value` 注入 / fixture |
| 🔴 代码注释（仅文案）        |      2 |      4 | sed 文案改                 |
| 🟡 配置                      |     10 |     20 | 人工 verify 后改           |
| 🟢 文档引用                  |     18 |     43 | sed 批量替换               |
| **合计**                     | **26** | **69** | —                          |

#### 1.1 🔴 真代码硬编码（3 行 / 2 文件）

| 文件                                    |  行 | 改造                                 |
| --------------------------------------- | --: | ------------------------------------ |
| `agentcook-java/.../OpenApiConfig.java` |  42 | 抽 `@Value("${agentcook.docs.url}")` |
| `agentcook-java/.../OpenApiConfig.java` |  62 | 抽 `@Value("${agentcook.api.url}")`  |
| `e2e/app/full-user-journey.spec.ts`     |  40 | 抽 `process.env.E2E_ADMIN_USERNAME`  |

**为何归 🔴**：sed 替换可走但留下设计债（下次又换域名再 cascade）。本次顺手 refactor 抽 env，单点 fix 永久收益。

#### 1.2 🟡 配置（20 行 / 10 文件）

`.env`（12）/ Helm values（4）/ Swarm gateway（2）/ Java spec `info.url`（1）/ docs-site package.json description（1）。每处必须人工 verify 语义（CORS origin 须 `https://<NEW_DOMAIN>` 非裸域 / Helm `domain:` 被 Ingress + cert-manager + PrometheusRule 三处引用 / Traefik ACME `email:` 需作者真邮箱）。

#### 1.3 🟢 文档引用（43 行 / 18 文件）

Top 5：`production-configuration.md` (10) / `frontend-conventions.md` (7) / `k8s-operations-manual.md` (4) / `architecture/03-k8s-deployment.md` (3) / 其余 14 文件各 1-2 行。`find … -name '*.md' -exec sed -i ''` 一次批量；ADR 类（`ADR-006`/`ADR-013`/`ADR-016`/`ADR-018`/`draft-cloudflare-turnstile-rate-limit-design.md`）含 5 行命中按 ADR 不可篡改原则保留原文 + 加 v1.1 加注。

### 2. fact-check：grep 没命中的项（防 brief 脑补）

| 位置                               | 期望                 |                                                          实测 |
| ---------------------------------- | -------------------- | ------------------------------------------------------------: |
| `nginx.conf`                       | 反代 server_name     |                                0（工程用 Traefik 不用 nginx） |
| `SecurityConfig.java` CORS allow   | `*.<CURRENT_DOMAIN>` |                                0（CORS 集中在 Swarm gateway） |
| `JwtTokenIssuer.java` issuer field | `<CURRENT_DOMAIN>`   | **0**（`Jwts.builder().issuer("agentcook-java")` 用逻辑常量） |
| `application.yml` `*-url`          | `<CURRENT_DOMAIN>`   |                      0（`python-upstream-url` 已 env-driven） |
| Python 包全部                      | hardcoded URL        |                     0（Python 全走 env / Cloudflared tunnel） |

**揪 Day 60 草稿 1 处假设偏差**（按 memory `feedback-fact-check-before-finalize`）：

- 原草稿"风险 + 回滚"段提到 "JWT issuer 变更需要老用户重新登录"
- 实测：JWT issuer field 是字符串 `"agentcook-java"` 不是域名 → **域名迁移不需要改 JWT issuer**，老 token 仍可解码 + 验签
- 真风险：客户端 base URL 改 → 旧 SPA build 仍 fetch 旧域 → 30 天 308 redirect 期间体验降级（§4 风险表已正确列出）

### 3. Cascade 4 步（D + 协调员协作）

按依赖关系倒推，**先信任锚再外围**：

|  步 | Owner      | 内容                                                                                                                                                                                                                                                                                      | 成本估算  |
| --: | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
|   1 | D          | `OpenApiConfig.java` 抽 `@Value` × 2 + e2e env 抽 + `application.yml` 加 2 key + mvn test verify 0 退化 + commit                                                                                                                                                                          | **1.5 h** |
|   2 | 协调员     | Cloudflare 注册 `<NEW_DOMAIN>` + DNS TTL 60s 24h 前置 + Helm 3 values 改 + cert-manager 新 Certificate CR（SAN 双域 7 天）+ Swarm `traefik.yml` + `middlewares.yml` + 4 个 `.env` 改 + 前端 build 重发布                                                                                  | **3 h**   |
|   3 | 协调员     | `docs-site/.vitepress/config.ts` + `package.json` sed + Cloudflare Pages 自定义域绑定 `<NEW_DOMAIN>` + 触发 `mirror-gitee.yml` 同步检查                                                                                                                                                   | **1 h**   |
|   4 | D + 协调员 | `docs/api/java-v1.yaml` `info.url` mvn 重 export + CHANGELOG 加 `### v1.1.0 — domain migration <NEW_DOMAIN>` 段（按 VERSIONING-POLICY MINOR bump，因 client base URL 变化）+ DEPRECATION-POLICY 加 v1.0 → v1.1 condition（30 天 308 redirect grace）+ 18 个 .md 批量 sed（排除 5 个 ADR） | **2 h**   |
|     |            | **合计**                                                                                                                                                                                                                                                                                  | **7.5 h** |

### 4. 风险 + 回滚

| 风险                                                       | 概率  | 缓解                                                                                         |
| ---------------------------------------------------------- | ----- | -------------------------------------------------------------------------------------------- |
| DNS 切换瞬间 5xx 尖峰                                      | 🟡 中 | TTL 60s 24h 前置；03:00-05:00 流量低谷切；旧域保留 30 天 308 redirect                        |
| 旧 SPA build 客户端 fetch 旧域 → 30 天 redirect 期体验降级 | 🟡 中 | 提前 7 天邮件 + 登录页 banner "<…> 即将迁移到 <NEW_DOMAIN>"；旧 build 30 天后强制 308 → 新域 |
| cert-manager HTTP-01 ACME 失败（新域真解析）               | 🟢 低 | 步 2 完成等 ACME 15 min；fallback Cloudflare Origin Cert                                     |
| Cloudflare Pages 自定义域绑定挂起 → docs 暂无              | 🟢 低 | 默认 `*.pages.dev` **永久保留**作为 fallback                                                 |
| Swagger UI client SDK auto-gen 拉旧 spec                   | 🟢 低 | 步 4 `java-v1.yaml` 与 Java commit 同 PR，CI `check-openapi-fresh.sh` 截停                   |
| `.env.production` hardcoded 漏改 → prod build 仍指旧域     | 🟡 中 | 步 2 末 grep verify `agentcook-{app,admin}/dist/` 0 命中旧域                                 |

**回滚触发**（任一即 rollback）：DNS 切换后 5min 错误率 > 5% / cert-manager 15min 未发新证 / Cloudflare Pages 30min 未绑定。

**回滚操作**：DNS 改回旧域（TTL 60s 已生效）+ `helm rollback agentcook` + 4 个 `.env` git revert + Pages 撤新域绑定。整体 < 10 min 回到 Day 60 状态。

### 5. Blue-Green 双域并存窗口

| 维度                   | T+0（切换日） | T+7（撤旧日）   | T+30                  |
| ---------------------- | ------------- | --------------- | --------------------- |
| DNS                    | 双解析        | 旧域 308 → 新域 | 同 T+7                |
| Helm Ingress           | 双 host SAN   | 单 host（新域） | 同 T+7                |
| 前端 `.env.production` | 新域          | 同 T+0          | 同 T+0                |
| 旧域行为               | 200 透明转    | 308 redirect    | 408 / 6mo 后 410 Gone |

### 6. 上线时机评估（D Buffer Day 64 主战决策）

| 选项                                        | 评估                                                                                                                                                       |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Buffer Day 65 末上线**                    | 🟡 紧 — cascade 4 步合计 7.5 h，留 0.5 h verify。需作者 Day 64 末或 Day 65 早晨开始才赶得上首发 D0（Day 70）。一旦任一步 fail，首发前 1 天 rollback 风险高 |
| **首发后 Phase 6 第 1 周（Day 70-72）上线** | 🟢 **本 ADR 推荐**                                                                                                                                         |

**推荐：首发后 Phase 6 第 1 周（Day 70-72）上线**

理由（按权重排）：

1. **首发 D0 风险隔离**：cascade 是 26 文件 / 69 行的全栈级动作。**不与首发同 sprint**。首发本来用 `<CURRENT_DOMAIN>`（已 stable 30+ 天，0 已知问题），不动它就赢一半
2. **D Buffer Day 64-65 释放给 Spring Boot 3.2.5 → 3.3.x spike**（D Phase 5 review §6 建议 1，清掉 Day 51 dep-check 64 高危 CVE 大半 — 这才是 D Buffer 能做完的"硬骨头"）
3. **30 天 grace period 给老用户**：首发 D0-D14 用 `<CURRENT_DOMAIN>` 收集反馈，Day 70 启 Phase 6 域名迁移；用户 bookmark 重置一次完成
4. **Cloudflare Pages 默认域永久兜底**：`*.pages.dev` 不撤，外部博客 / 教程 / Gitee mirror 链接 0 失效风险

## Consequences

### 正面

- **首发 Day 70 风险面缩小**：不动域名 = -1 个变量
- **D Buffer Day 64-65 真做 Spring Boot 3.3.x spike**（清 64 CVE 高 ROI）
- **Phase 6 第 1 周专门窗口**：可以 03:00-05:00 切换 + 7 天 Blue-Green observation
- 30 天 grace period 让老用户自然过渡

### 负面

- **首发 Day 70 时教程对外用 `<CURRENT_DOMAIN>`**，首发后 14 天切到 `<NEW_DOMAIN>` —— 首发博客 + GitHub Discussions 链接需要 308 redirect 兼容
- 旧域 30 天 308 + 6 个月 410 Gone 维护期较长（但都是 Cloudflare DNS 一行配置，0 人工）
- Phase 6 第 1 周 D 主战，与 v1.1 Anthropic provider 后续维护 / 50 博客系列启动并行

### 中性

- 域名迁移本身是一次性投资，迁完后下次再换域名的成本由本次 §1.1 的 refactor 减半（OpenApiConfig 抽 `@Value` 后下次只改 `application.yml`）

## Validation（Phase 6 第 1 周实施后）

按 cascade 4 步落地后，下列 grep 必须命中 0：

```bash
# Phase 6 D+X 末（迁移完成 day）
cd /Users/yvan/workspace/accio-work/agentcook-cc
grep -rn "<CURRENT_DOMAIN>" . \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=target --exclude-dir=__pycache__ \
  --exclude-dir=docs/adr 2>/dev/null | grep -v "^Binary"
# 期望：0 命中（ADR 段保留原文 + v1.1 加注，所以排除 docs/adr）
```

## Source

- `docs/adr/draft-laoa-dev-cascade-impact.md` 206 行（Day 60 末 D 起草 / 本 ADR 升级前身）
- `docs/api/VERSIONING-POLICY.md` §"Bump procedure (minor)" — 域名迁移按 MINOR 处理（client base URL 变化 = 行为变化）
- `docs/api/DEPRECATION-POLICY.md` §"v1 → v2 migration path" — 6 个月 sunset 不适用（这不是 v2，是域名迁移），用 30 天 + 6 个月 308 redirect window 替代
- `_internal/audit/phase5-review-2026-06-03-agent-d.md` §6 建议 — D Buffer Day 58/63/64-65 任务分配

## Related

- ADR-006: Blue-Green deployment — 双域并存 7 天复用 ADR-006 思路
- ADR-013: Java business backend — Java spec `info.url` 与 Python spec 独立迁移（双 spec 模式）
- backlog #11（Cloudflare Turnstile + Rate Limit）— Day 62 已完工 / 与本 ADR 互补：Turnstile gate + 30 天 grace redirect 一起防滥用
