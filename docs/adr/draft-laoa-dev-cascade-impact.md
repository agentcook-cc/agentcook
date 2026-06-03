# Draft ADR — `<NEW_DOMAIN>` cascade impact analysis

**Status**: Draft / Buffer Day 64-65 评估输出 / 待作者拍板上线时机
**Date**: 2026-06-03（Buffer Day 60 末）
**Authors**: Agent D（Java/API 主战）+ 协调员
**Scope**: 评估"购入 `<NEW_DOMAIN>` 替换工程内部 `<CURRENT_DOMAIN>` + Cloudflare Pages 镜像域"的 cascade 改动范围。**impact analysis only — 不真改代码**。

---

## 1. Context

Phase 4.5 真上线推迟到首发前（作者 2026-06-01 GO）。Buffer Day 64-65 要给出"买新域名 → 全栈替换"的可执行 cascade 与风险评估。本 ADR 走的是 impact analysis，**不动 .env / 不跑 cf-cli / 不 helm upgrade**。

工程当前外露的域名标识有三种：

1. `<CURRENT_DOMAIN>`（工程默认主域，以及 `staging.<…>` 与 `api.<…>` 子域）
2. `<CURRENT_DOCS_DOMAIN>`（Cloudflare Pages 默认提供的 docs 镜像域）
3. （新域名 `<NEW_DOMAIN>` — 本 cascade 的目标，未购入）

目标：把 1、2 替换为 `<NEW_DOMAIN>` 体系，保留 Cloudflare Pages 默认域 7 天作为 fallback。

---

## 2. Source（grep 实测 stdout，防协调员脑补）

```bash
cd /Users/yvan/workspace/accio-work/agentcook-cc && \
  grep -rn "agentcook\.cc\|agentcook-docs\.pages\.dev\|agentcook\.pages\.dev" . \
       --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=target --exclude-dir=__pycache__ \
       2>/dev/null | wc -l
# → 69 行命中 / 26 个文件
```

按 file extension 分布（实测 top）：

```
10  docs/devops/production-configuration.md
 7  agentcook-design-tokens/docs/frontend-conventions.md
 4  docs/devops/k8s-operations-manual.md
 3  agentcook-{app,admin}/.env.{staging,production}（4 文件 × 3 行 = 12）
 3  docs/architecture/03-k8s-deployment.md
 2  deploy/helm/agentcook/values.yaml
 2  docs-site/.vitepress/config.ts
 2  tests/performance/PERFORMANCE-REPORT.md
 2  docs/api/DEPRECATION-POLICY.md
 2  docs/adr/ADR-006-blue-green-deployment.md
 2  docs-site/DEPLOY.md
 2  agentcook-app/README.md
 2  agentcook-java/agentcook-api/.../OpenApiConfig.java
 1  …（其余 13 文件各 1 行）
```

---

## 3. 分类清单（按改动复杂度）

| 类                           | 文件数 |   行数 | 处理方式                   |
| ---------------------------- | -----: | -----: | -------------------------- |
| 🔴 代码硬编码（真 refactor） |      2 |      3 | 抽 `@Value` 注入 / fixture |
| 🔴 代码注释（仅文案）        |      2 |      4 | sed 文案改                 |
| 🟡 配置                      |     10 |     20 | 人工 verify 后改           |
| 🟢 文档引用                  |     18 |     43 | sed 批量替换               |
| **合计**                     | **26** | **69** | —                          |

注：以下 4 行落在代码文件里但本质是注释（`//`、`*` 描述），归到 🔴-注释子类，replacement 与 🟢 同款 sed 即可：

- `docs-site/.vitepress/config.ts:4,6`（VitePress CNAME 注释）
- `tests/performance/k6/full-ramp.js:26`（usage example 注释）

### 3.1 🔴 真代码硬编码（3 行 / 2 文件）

| 文件                                                  |  行 | 内容（脱敏后）                                 | 改造                                                |
| ----------------------------------------------------- | --: | ---------------------------------------------- | --------------------------------------------------- |
| `agentcook-java/agentcook-api/.../OpenApiConfig.java` |  42 | `Contact().url("https://<CURRENT_DOMAIN>")`    | 抽 `@Value("${agentcook.docs.url}")`                |
| `agentcook-java/agentcook-api/.../OpenApiConfig.java` |  62 | `Server().url("https://api.<CURRENT_DOMAIN>")` | 抽 `@Value("${agentcook.api.url}")`                 |
| `e2e/app/full-user-journey.spec.ts`                   |  40 | `ADMIN_USERNAME = "admin@<CURRENT_DOMAIN>"`    | 抽 `process.env.E2E_ADMIN_USERNAME`，默认走 fixture |

**为何归 🔴**：这三处 build-time / runtime 行为依赖硬编码字符串，sed 替换可走但留下设计债（下次再换域名又是 cascade）。建议本次 cascade 顺手 refactor 抽 env，**单点 fix 永久收益**。

### 3.2 🟡 配置文件（20 行 / 10 文件）

| 类目          | 文件                                                                                    | 行数 |
| ------------- | --------------------------------------------------------------------------------------- | ---: |
| .env          | `agentcook-app/.env.{staging,production}` + `agentcook-admin/.env.{staging,production}` |   12 |
| Helm          | `deploy/helm/agentcook/{values,values-staging,values-prod}.yaml`                        |    4 |
| Swarm gateway | `agentcook-swarm/gateway/traefik.yml` + `middlewares.yml`                               |    2 |
| Java spec     | `docs/api/java-v1.yaml`（`info.url`）                                                   |    1 |
| package.json  | `docs-site/package.json` description                                                    |    1 |

**为何 🟡 而非 🟢**：每处必须人工 verify "新值是否符合该层语义"（CORS origin 须 `https://<NEW_DOMAIN>` 不能裸域；Helm `domain:` 字段会被 Ingress / cert-manager / PrometheusRule 三处引用；Traefik ACME `email:` 需作者真邮箱）。

### 3.3 🟢 文档引用（43 行 / 18 文件）

Top 5：`production-configuration.md` (10) / `frontend-conventions.md` (7) / `k8s-operations-manual.md` (4) / `architecture/03-k8s-deployment.md` (3) / 其余 14 文件各 1-2 行。

**处理**：`find … -name '*.md' -exec sed -i ''` 一次批量。但 ADR 类（`ADR-006`/`ADR-013`/`ADR-016`/`ADR-018`/`draft-cloudflare-turnstile-rate-limit-design.md`）含 5 行命中，按 ADR 不可篡改原则，**保留原文 + 加 v1.1 加注**，不直接 sed。

### 3.4 fact-check：grep 没命中的项（防协调员脑补）

按 brief "不脑补假设"要求，已 grep verify 以下"应该有"的位置实际**为 0 命中**：

| 位置                                                                                 | 期望                 | 实测 | 解读                                                                                                                                                    |
| ------------------------------------------------------------------------------------ | -------------------- | ---: | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nginx.conf` / `nginx/*.conf`                                                        | 反代 server_name     |    0 | 工程未使用 nginx —— gateway 走 Traefik（命中已计入 🟡）                                                                                                 |
| `SecurityConfig.java` CORS allow list                                                | `*.<CURRENT_DOMAIN>` |    0 | CORS 在 Swarm gateway `middlewares.yml` 集中管，Java 不重复                                                                                             |
| `JwtTokenIssuer.java` issuer field                                                   | `<CURRENT_DOMAIN>`   |    0 | `Jwts.builder().issuer("agentcook-java")` 用逻辑常量，**不依赖域名** —— 域名迁移**不需要**改 JWT issuer，brief §强约束"JWT issuer 变更"假设有偏差，flag |
| `application.yml` `agentcook.*-url`                                                  | `<CURRENT_DOMAIN>`   |    0 | 当前 `python-upstream-url` 走 `${PYTHON_UPSTREAM_URL:http://localhost:8000}`，**已是 env-driven**，cascade 改 env 即可                                  |
| `agentcook-core/` `agentcook/` `agentcook-providers/` `agentcook-storage/` Python 包 | hardcoded URL        |    0 | Python 后端 0 命中域名 —— Python 全走 env / Cloudflared tunnel，**A 领地无 cascade 改动**                                                               |

**揪 brief 1 处假设偏差**（按 memory `feedback-fact-check-before-finalize`）：

- brief §"风险 + 回滚"提到 "JWT issuer 变更需要老用户重新登录"
- 实测：JWT issuer field 不是域名，是字符串 `"agentcook-java"`（逻辑标识）
- 真相：**域名迁移不需要改 JWT issuer**，老 token 仍可解码 + 仍可验签
- 真风险：客户端 base URL 改 → 旧 SPA build 仍 fetch 旧域 → 30 天 308 redirect 期间体验降级（已在 §5 风险表正确列出）

---

## 4. Cascade 改动顺序（D + 协调员协作）

按依赖关系倒推，**先信任锚，再外围**：

### 步 1 — D 主战：Java + e2e（独立可验证）

- `OpenApiConfig.java` line 42/62：抽 `@Value` 注入，`application.yml` 加 `agentcook.docs.url` / `agentcook.api.url` 两键，默认走 `https://<NEW_DOMAIN>` / `https://api.<NEW_DOMAIN>`
- 同步评估 CORS：`SecurityConfig` 当前 CORS allow 在 `agentcook-swarm/gateway/dynamic/middlewares.yml` 而非 Java（已 grep 验证 — `SecurityConfig.java` 0 命中域名）
- 同步评估 JWT issuer：当前 `JwtTokenIssuer.issuer("agentcook-java")` 是逻辑常量（非域名），**不需要改**
- `e2e/app/full-user-journey.spec.ts:40`：抽 `E2E_ADMIN_USERNAME` env
- mvn test + e2e dryrun 验证 0 退化
- commit / 等步 2

### 步 2 — 协调员主战：DNS / Helm / Ingress / Gateway

- Cloudflare：注册 `<NEW_DOMAIN>` → DNS A/CNAME 指 prod IP（TTL 60s **24h 前置**）
- Helm `values.yaml`/`values-prod.yaml`/`values-staging.yaml`：`global.domain` + `ingress.hosts[0].host` 改 `<NEW_DOMAIN>` / `staging.<NEW_DOMAIN>`
- cert-manager：新 Certificate CR（SAN 含旧/新两域 → 7 天 Blue-Green 期间双证书都有效）
- Swarm `traefik.yml` ACME email + `middlewares.yml` CORS origin 加 `https://<NEW_DOMAIN>`（旧域同步保留）
- 4 个 `.env` 文件：staging / prod 三个 `VITE_*_API_BASE_URL` 改新域；前端 build 重发布到 Pages

### 步 3 — 协调员：docs-site + Cloudflare Pages

- `docs-site/.vitepress/config.ts` 注释 + `package.json` description sed 替换
- Cloudflare Pages 项目 custom domain 加 `<NEW_DOMAIN>` → 7 天后撤旧 `<CURRENT_DOCS_DOMAIN>` 自定义域绑定（Pages 默认 `*.pages.dev` 仍保留作为永久 fallback）
- 触发一次 GitHub Actions `mirror-gitee.yml` 同步检查

### 步 4 — D + 协调员：API spec + CHANGELOG

- `docs/api/java-v1.yaml` `info.url` 更新（mvn 重 export 自动跑，**不要手改**）
- `docs/api/CHANGELOG.md` 加 `### v1.1.0 — domain migration <NEW_DOMAIN>` 段（按 VERSIONING-POLICY 这是 PATCH bump，因为只是 metadata 改；但 client base URL 改 = 行为变化，建议按 MINOR 处理，`info.version` 1.0.0 → 1.1.0）
- `docs/api/DEPRECATION-POLICY.md` 加 "v1.0 → v1.1 域名迁移" condition（30 天兼容期内 old `<CURRENT_DOMAIN>` 仍 200，第 31 天 308 redirect 到新域 6 个月，第 7 个月起 410 Gone）
- 18 个文档文件批量 sed（排除 5 个 ADR — ADR 保留原文加 v1.1 加注）

---

## 5. 风险 + 回滚

| 风险                                                                                                 | 概率  | 缓解                                                                                                     |
| ---------------------------------------------------------------------------------------------------- | ----- | -------------------------------------------------------------------------------------------------------- |
| DNS 切换瞬间 5xx 尖峰                                                                                | 🟡 中 | TTL 60s **24h 前置**；切换在 03:00-05:00 流量低谷；旧域保留 30 天 308 redirect                           |
| JWT issuer 字段不是域名，但客户端 base URL 改 → 旧 token 仍可解码但 fetch 失败                       | 🟡 中 | **提前 7 天**邮件公告 + 在前端登录页加 banner "<…> 即将迁移到 <NEW_DOMAIN>"；旧 SPA build 仍指旧域 30 天 |
| Helm `values.yaml domain` 改后 cert-manager 等 LetsEncrypt issue 失败（HTTP-01 ACME 必须新域真解析） | 🟢 低 | 步 2 完成后等 ACME 15 min；fallback 用 Cloudflare Origin Cert（永不过期）                                |
| Cloudflare Pages 自定义域绑定挂起 → docs 暂时无法访问                                                | 🟢 低 | 默认 `*.pages.dev` 域**永久保留**作为 fallback，外部博客链接已含                                         |
| Swagger UI client SDK auto-gen 拉旧 spec → 字段名/URL 不一致                                         | 🟢 低 | 步 4 `java-v1.yaml` 与 Java commit 同 PR，CI `check-openapi-fresh.sh` 截停                               |
| `.env.production` 含 hardcoded `https://<CURRENT_DOMAIN>` 漏改 → 前端 prod build 还指旧域            | 🟡 中 | 步 2 末 grep verify `agentcook-{app,admin}/dist/` 0 命中旧域                                             |

**回滚条件**（任一即 rollback）：DNS 切换后 5min 错误率 > 5% / cert-manager 15min 未发新证 / Cloudflare Pages 30min 未绑定。

**回滚操作**：DNS 改回旧域（TTL 60s 已生效）+ Helm `helm rollback agentcook` + 4 个 `.env` git revert + Pages 撤新域绑定。整体 < 10 min 全部回到 Day 60 状态。

---

## 6. Blue-Green 双域并存 7 天

| 维度                    | Day T+0（切换日）                                 | Day T+7（撤旧日）                          | Day T+30                |
| ----------------------- | ------------------------------------------------- | ------------------------------------------ | ----------------------- |
| DNS                     | `<NEW_DOMAIN>` 真解析 / `<CURRENT_DOMAIN>` 仍 200 | `<CURRENT_DOMAIN>` 改 308 → `<NEW_DOMAIN>` | （同 T+7）              |
| Helm Ingress            | 双 host SAN                                       | 单 host（新域）                            | 同 T+7                  |
| 前端 .env.production    | `<NEW_DOMAIN>`                                    | 同 T+0                                     | 同 T+0                  |
| API spec `info.url`     | `<NEW_DOMAIN>`                                    | 同 T+0                                     | 同 T+0                  |
| `<CURRENT_DOMAIN>` 行为 | 200 透明转                                        | 308 redirect                               | 408 / 6 个月后 410 Gone |
| 用户重登提示            | banner 提示                                       | 同 T+0                                     | （消失）                |

---

## 7. 评估结论

| 选项                     | 推荐                                                                                                                                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Buffer Day 65 末上线** | 🟡 紧 — 步 1+2+3+4 估 1-1.5 天，留 0.5 天 verify。**需作者 Day 64 晨开始**才赶得上                                                                                                                                                    |
| **首发后 Phase 6 上线**  | 🟢 **D + 协调员推荐** — 首发本来就用 `<CURRENT_DOMAIN>` + `<CURRENT_DOCS_DOMAIN>`（已 stable 30+ 天），cascade 改造留 Phase 6 第 1 周窗口期；新用户首发后已熟悉旧域，迁移公告效果更好；DNS / cert / Pages 三段任一出问题不影响首发 D0 |

### 推荐：**首发后 Phase 6 第 1 周（Day 70-72）上线**

理由（按权重）：

1. **首发 D0 风险隔离**：cascade 是 26 文件、69 行的全栈级动作，**不与首发同 sprint**；首发已就绪（Phase 5 review GO），不动它就赢了一半
2. **D Buffer Day 64-65 释放给 Spring Boot 3.2.5 → 3.3.x spike**（D Phase 5 review §6 建议 1，dep-check 64 高危 CVE 集中清掉）—— 这才是 D 唯一能在 Buffer 做完的"硬骨头"
3. **30 天 grace period 给老用户**：首发期间用 `<CURRENT_DOMAIN>` 收集 7-14 天反馈，再启 Phase 6 域名迁移；用户重登 + bookmark 重置一次完成
4. **Cloudflare Pages 默认域永久兜底**：`*.pages.dev` 不撤，外部博客/教程链接 0 失效风险

---

## 8. Related

- `docs/api/VERSIONING-POLICY.md` §"Bump procedure (minor)" — 域名迁移按 MINOR 处理（client base URL 变 = 行为变化）
- `docs/api/DEPRECATION-POLICY.md` §"v1 → v2 migration path" — 6 个月 sunset 不适用（这不是 v2，只是域名迁移）；用 30 天 + 6 个月 308 redirect window 替代
- `docs/adr/ADR-006-blue-green-deployment.md` — 双域并存 7 天复用 ADR-006 思路
- `docs/adr/ADR-013-java-business-backend.md` — Java spec `info.url` 与 Python spec 独立迁移（双 spec 模式）
- `_internal/audit/phase5-review-2026-06-03-agent-d.md` §6 建议 — D Buffer Day 58/63/64-65 任务分配
