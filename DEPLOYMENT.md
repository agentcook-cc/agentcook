# agentcook 部署总览

> **一句话**:agentcook 提供 **3 档部署方案**,从本地 docker compose 起步,到 Cloudflare 免费 MVP,再到 K8s Helm 商业级 prod —— **按你"要给谁看"来选档**,文档全部公开。

---

## TL;DR(30 秒选档)

| 你的场景                          | 选                          | 投入                         | 文档入口                                                                                                                                        |
| --------------------------------- | --------------------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 自己跑通教程 / 朋友看一眼         | **L1 本地 docker compose**  | ¥0 / ~30 min                 | [本文 §1](#l1--本地-docker-compose30-min) → [Makefile](Makefile)                                                                                |
| 演示给同行 / 教程读者跟着跑 demo  | **L2 Cloudflare Pages MVP** | ¥0 / ~40 min                 | [本文 §2](#l2--cloudflare-pages-mvp40-min) → [docs/devops/L2-cloudflare-pages-mvp-cookbook.md](docs/devops/L2-cloudflare-pages-mvp-cookbook.md) |
| 真商业级上线 / 多人协作 / on-call | **L3 K8s Helm prod**        | ¥500-2000/月 / ~7.5h cascade | [本文 §3](#l3--k8s-helm-prod7-5h-cascade) → [docs/devops/](docs/devops/) 4 文档                                                                 |

> 不知道选哪档?看 [§4 选档决策树](#4-选档决策树)。

---

## 0. 3 档对照速查

| 维度                  | L1 docker compose                  | L2 Cloudflare MVP                        | L3 K8s Helm prod                                                                                               |
| --------------------- | ---------------------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **启动时间**          | ~30 min                            | ~40 min                                  | ~7.5h cascade(首次)                                                                                            |
| **月费(基础设施)**    | ¥0(本地)                           | ¥0(Cloudflare 免费 tier + Qwen 免费额度) | ¥500-2000(RDS + ElastiCache + K8s 集群)                                                                        |
| **公网可访问**        | ❌(localhost only)                 | ✅(`*.pages.dev` + `cloudflared tunnel`) | ✅(真域名 + TLS)                                                                                               |
| **服务数**            | 9 个 docker 服务                   | 同 L1 + Cloudflare Pages                 | 5 个 Helm deployment + 托管基础设施                                                                            |
| **Blue-Green 切流量** | ❌                                 | ❌                                       | ✅(详 [ADR-006](docs/adr/ADR-006-blue-green-deployment.md))                                                    |
| **监控告警**          | 本地 Jaeger + Prometheus(no alert) | 同 L1                                    | ✅ 9 alerts(HTTP 5xx / p99 / pod restart / OOM / CPU / LLM cost / chat fail / turnstile fail / rate-limit hit) |
| **on-call runbook**   | —                                  | —                                        | ✅ [troubleshooting-runbook.md](docs/devops/troubleshooting-runbook.md) 410 行                                 |
| **适合谁**            | 教程读者跑通 / 本地开发            | demo 推广早期 / 简历作品集               | 真商业级 / 多人协作 / SLA                                                                                      |
| **可逆性**            | 一键 `make clean`                  | 一键删 Cloudflare 项目                   | 完整 Helm rollback + Blue-Green 双域并存 7 天                                                                  |

---

## L1 — 本地 docker compose(30 min)

**核心**:9 个 docker 服务一键拉起(postgres / postgres-business / redis / jaeger / prometheus / pact-broker / pact-broker-db / langfuse / agentcook-java),本机 `localhost` 跑通完整 agentcook。

### 前置

- Python 3.11+、[uv](https://docs.astral.sh/uv/) 包管理器
- Java 17+、Maven Wrapper(`./mvnw`,已内置)
- Docker(推荐 colima)+ docker compose v2
- Node.js 20+、pnpm 9+

### 启动

```bash
# 1. 安装 Python 依赖(必须带 --all-packages --all-extras,缺一会让 chat / OTEL trace 静默失败)
uv sync --all-packages --all-extras --group dev

# 2. 启动全部服务(docker-compose + Python app)
make dev

# 3. 验证
curl http://localhost:8000/health     # agentcook Python(真路径 /health,不是 /healthz)
open http://localhost:5173            # admin Vue 端
open http://localhost:5174            # app React 端
open http://localhost:16686           # Jaeger 链路追踪
```

完整端口表 + 常用命令见 [README.md §开发者快速上手](README.md#开发者快速上手)。

### 何时升级到 L2

- 想给别人发个公网链接看一眼 → 走 L2
- 公司同行 review → 走 L2 + Cloudflare Access 加 SSO

---

## L2 — Cloudflare Pages MVP(40 min)

**核心**:用 Cloudflare Pages 免费 `*.pages.dev` subdomain + `cloudflared tunnel` 把本地 Python 后端暴露公网,**总成本 ¥0**(Cloudflare 免费 tier + Qwen 免费额度)。

### 推荐路径

| 步骤                                                      | 文档                                                                                               | 时长           |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | -------------- |
| 1. 完整 cookbook(决策时间线 + 5 踩坑实录)                 | [docs/devops/L2-cloudflare-pages-mvp-cookbook.md](docs/devops/L2-cloudflare-pages-mvp-cookbook.md) | 通读 ~10 min   |
| 2. wrangler 真 deploy SOP(brew/npm 安装 + login + deploy) | [docs/devops/L2-wrangler-deploy-sop.md](docs/devops/L2-wrangler-deploy-sop.md)                     | 真执行 ~30 min |

### 何时升级到 L3

- 想要真域名(`*.dev` / `*.ai` / `*.com`)
- 需要 Blue-Green 切流量、零停机滚动升级
- 想要 on-call 告警(HTTP 5xx / p99 latency / LLM 费用)
- 团队多人协作 / 有 SLA 承诺

---

## L3 — K8s Helm prod(7.5h cascade)

**核心**:K8s 5 服务微服务 + Helm chart 13 templates + Blue-Green 切流量 + Cloudflare 全套(DNS / Pages / Workers)+ on-call 告警。

### 4 份生产文档(共 1,375 行)

| 文档                                                                               |  行 | 用途                                                                                          |
| ---------------------------------------------------------------------------------- | --: | --------------------------------------------------------------------------------------------- |
| [docs/devops/production-configuration.md](docs/devops/production-configuration.md) | 381 | 5 服务完整配置(env / secret / resource / probe / HPA / PDB / NetworkPolicy / Blue-Green 步骤) |
| [docs/devops/k8s-operations-manual.md](docs/devops/k8s-operations-manual.md)       | 353 | K8s 日常运维(deploy / upgrade / rollback / 扩缩容 / 排查)                                     |
| [docs/devops/troubleshooting-runbook.md](docs/devops/troubleshooting-runbook.md)   | 410 | 故障 runbook(8 类故障 × 诊断 → 处置 → 复盘)                                                   |
| [docs/devops/monitoring-alerts-sop.md](docs/devops/monitoring-alerts-sop.md)       | 231 | 7 alert SOP(分级 / 触发条件 / 处置流程)                                                       |

### 配套架构决策

| ADR                  | 主题                                                 |
| -------------------- | ---------------------------------------------------- |
| [ADR-005](docs/adr/) | Observability(OTel + Jaeger + Prometheus + Langfuse) |
| [ADR-006](docs/adr/) | Blue-Green deployment                                |
| [ADR-016](docs/adr/) | 默认 LLM Provider(Qwen)                              |
| [ADR-019](docs/adr/) | 域名迁移 cascade(7.5h 详细分解)                      |

### 7.5h cascade 概览

| 步  | 谁          | 时长 | 事                                              |
| --- | ----------- | ---- | ----------------------------------------------- |
| 1   | 后端        | 1.5h | Java application.yml + CORS + JWT issuer        |
| 2   | DevOps      | 3h   | K8s ingress + Cloudflare DNS + Helm values-prod |
| 3   | DevOps      | 1h   | docs-site VitePress + Cloudflare Pages 重指向   |
| 4   | 后端+DevOps | 2h   | API CHANGELOG + Blue-Green 双域并存 7 天        |

完整 SOP 详见上述 4 份文档 + ADR-019。

---

## 4. 选档决策树

```
你打算给谁看?
├─ 只给自己 / 朋友 → L1 docker compose
│
├─ 给同行 demo / 简历作品集 / 教程读者跟着跑
│   │
│   ├─ 不想买域名 / 只想免费验证一周 → L2 Cloudflare Pages MVP
│   │
│   └─ 已经准备好买域名 + 长期维护 → 跳过 L2 直接 L3
│
└─ 真商业级 / 多人协作 / 7×24 SLA → L3 K8s Helm prod
```

### 何时**不要**选 L3

- 没有 ~¥500-2000/月预算
- 没人愿意做 on-call(凌晨 3 点起来处理 alert)
- 还在快速迭代产品形态,接口没稳定 → L2 够用

### 何时**必须**选 L3

- 有付费用户 / 商业合约 SLA
- 数据合规要求(等保 / GDPR 数据驻留)
- 团队 >3 人,需要多环境隔离(dev / staging / prod)

---

## 5. 配套教程

📚 教程主仓:[agentcook-cc/agentcook-tutorial](https://github.com/agentcook-cc/agentcook-tutorial) — 《从 0 到 1 构建商业级 AI Agent 产品》

教程里 **第 20 讲(发布与运营)** + **第 25 讲(上线最后一公里)** 是本文的教程级叙事版,适合先看完教程再来本文找 SOP。

读者反向跑通本文 3 档 = 教程闭环的最终验收。

---

## 6. 反馈 / 求助

- 跑 L1 不通 → [GitHub Issue](https://github.com/agentcook-cc/agentcook/issues)(用 "L1 deployment" 模板)
- 跑 L2 不通 → 同上 + 附 cookbook 里第几步卡住
- L3 上线 cascade 中有疑问 → [GitHub Discussions](https://github.com/agentcook-cc/agentcook/discussions)(`deployment` 分类)

---

**最后更新**:2026-06-04(Day 70+ 首发期 / Phase 6 P1 MVP 阶段)
