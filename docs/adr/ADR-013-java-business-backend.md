# ADR-013: agentcook-java 业务后端(DDD 四层 + Spring Boot 3)

## Status

Accepted (2026-05-19)

> **来源**:Day 11 Critical Finding **CF-3** — 教程 03/04/06 讲明确写 "网关 Java Spring WebFlux + 业务后端 Java Spring Boot + DDD 四层",但 roadmap.md / ADR-001 选型时漏选 Java,实际 agentcook-cc 仓库**只有 Python**,教程承诺未兑现。Day 11 grep 核实暴露,作者拍 B 全量方案补齐。

## Context

### CF-3 教程-工程不一致(grep 实据)

| 教程章节 | 明确写的技术栈 |
|---|---|
| **03 从用户故事到架构** | "网关 Java + Spring WebFlux / 业务后端 Java + Spring Boot / DDD 四层(api/application/domain/infrastructure)" |
| **04 请求生命周期** | "网关 Java Spring WebFlux(端口 8080)" |
| **06 网关层** | "最简单的实现——用 Java 写个路由器" |
| **压测 P3 报告** | (虚拟前端读者)看到的就是 "教程推荐 Python FastAPI + Java Spring Boot" |

**实际仓库矩阵**:9 个 agentcook-* 包**全是 Python**(`agentcook` Python FastAPI 主壳替代了教程承诺的 Java 业务后端),**没有任何 Java 业务后端仓库**。

读者(尤其阿里 Java P7 受众)跟着教程做时会发现:
- 教程 03 讲承诺的 "Java DDD 四层" → GitHub 看不到 = **教程在撒谎**
- 阿里 / 蚂蚁 / 字节系受众价值打折(Java 是主流栈)

**原因复盘**:教程基于早期 phoenix 原型(Java + Kotlin)写;v6.0 战略升级(2026-05-15)roadmap / ADR-001 重选 Python(LangChain 生态);但**没人同步改教程**(教程稳态被冻结);**也没有 ADR 显式声明"为什么从双后端改成只 Python"** — 决策溯源断了。

### 为什么 Python 不够

| 缺口 | 影响 |
|---|---|
| 企业级业务后端 DDD 实践 | 教程"产品架构师判断力"少一个核心案例 |
| 阿里 / 大厂 Java 受众 | agentcook 求职作品集对 Java P7+ 投递回复率打折 |
| Phoenix 真实生产经验脱敏复用 | 作者(P7)最大资产没用上 |
| 教程信用 | 03/04/06 讲承诺未兑现 → 读者信任损耗 |

## Decision

### 1. 新增 `agentcook-java` 仓库(Phase 2 起跑)

**技术栈**:
- Java 17(LTS,与 phoenix-server 一致)
- Spring Boot 3.x
- Spring Cloud Gateway(网关层)/ Spring WebFlux(响应式 SSE)
- Spring Data JPA + PostgreSQL 16 + Flyway(migration)
- Spring Security + OAuth2 Resource Server(配合 B3 JWT 双 token)
- Maven multi-module(workspace 管理)

### 2. DDD 四层模块结构

```
agentcook-java/
├── pom.xml(parent)
├── api/                    ← Controller + DTO + OpenAPI 文档生成
│   └── pom.xml
├── application/            ← Use cases + Application Service + Transaction
│   └── pom.xml
├── domain/                 ← Aggregate Root + Domain Service + Domain Event
│   └── pom.xml
└── infrastructure/         ← JPA Repository + Redis client + MQ + 外部集成
    └── pom.xml
```

**5-7 个 domain 聚合**(Phase 2 Day 18-20 finalize):
- User(用户 + 认证)
- Session(对话会话)
- Plugin(Plugin 注册 + 权限)
- Connector(IM 渠道接入)
- Permission(RBAC + 资源授权)
- (待 Phase 2 决)Workspace / Audit Log

### 3. 与 Python 主壳的接口约定

| 维度 | Python `agentcook` 主壳 | Java `agentcook-java` 业务后端 |
|---|---|---|
| **职责** | Agent runtime(LLM 调用 / Memory / multi-agent / Plugin 沙箱) | 业务实体生命周期 / 权限 / Connector / 审计 / RBAC |
| **对外 API** | REST `/api/v1/agent/*` `/api/v1/memory/*` | REST `/api/v1/users/*` `/api/v1/sessions/*` `/api/v1/plugins/*` `/api/v1/connectors/*` `/api/v1/permissions/*` |
| **内部通信** | 接收 Java 业务调用 — Python expose gRPC `AgentRuntimeService`(Day 24 Pact 契约冻结) | 调用 Python — Java 用 grpcio + Spring gRPC client |
| **数据库** | `agentcook` DB(memory_events / agents / sessions_runtime) | `agentcook_business` DB(users / plugins / connectors / permissions / audit_log) |
| **共享 schema** | OpenAPI spec 在 `docs/api/v1.yaml`(Day 24 冻结) | 同 spec 生成 Java DTO(openapi-generator) |

**关键边界**(防交叉污染):
- Java **不写 LLM 调用 / 不写 Memory / 不写 Plugin 沙箱**(那是 Python 主壳的职责)
- Python **不写 User CRUD / 不写 RBAC / 不写 Connector OAuth**(那是 Java 业务后端的职责)
- 共享只通过 **gRPC + OpenAPI spec**(契约稳定)

### 4. 4 Agent 协作模式启动

新增 **Agent D(Java 架构师)** — Phase 2 Day 16 起跑,详 `_internal/agent-roles/agent-d-java-architect.md`。

| Agent | 角色 | Phase 2 起工作量 |
|---|---|---|
| A | Python 主架构师 | Python core / providers / storage / 主壳 / swarm |
| B | 前端开发 | design tokens / admin / app |
| C | DevOps + 测试 | CI/CD / K8s / Pact / e2e / 测试金字塔 |
| **D**(新)| Java 业务后端架构师 | agentcook-java DDD 四层 / Spring Boot 3 / 与 Python 主壳 gRPC 集成 |

**作者 sync 时间**:60-110 分钟/天 → **75-130 分钟/天**(增 25-30%),由 integration-handbook.md 4 Agent SOP 管理。

### 5. 周期影响

| 维度 | 原(3 Agent Python only) | 现(4 Agent + Java) |
|---|---|---|
| 总 calendar day | 30-45 | **35-50**(+5 day 调整 buffer) |
| 上线时间(demo.agentcook.cc) | Phase 4 Day 45-46 | Phase 4 Day 48-50 |
| 教程发布起点 | Day 70+ | Day 75+ |
| 2026-12-01 全套交付 | 保持 | **保持**(Buffer 吸收) |

### 6. Agent D 启动节奏

- **Day 11-15**:Phase 1 后半正常推进(A/B/C),Agent D 不启动 — 准备 spring boot + maven 学习材料(实际 D 是 Claude Code 助手,不需学习)
- **Day 16 起**:Agent D 加入,与 A 同步起跑 Phase 2(A 写 Agent Core 9 模块,D 写 Java skeleton + DDD domain 层)
- **Day 24**:关键交接点 — A 冻结 OpenAPI spec → D 生成 Java DTO + Controller
- **Day 26-37 (Phase 3)**:D 完善 application 层 + 双后端联调
- **Day 38-47 (Phase 4)**:D 与 C 协作部署 Java app 到 K8s + 与 Python swarm 协调
- **Day 48-57 (Phase 5)**:D 测试 / 性能 / 文档

## Consequences

### Positive
- ✅ **教程信用恢复** — 03/04/06 讲承诺兑现,读者能在 GitHub 看到真 Java DDD 四层
- ✅ **作者简历价值最大化** — Phoenix 真实生产经验脱敏复用(Java + DDD)+ 双后端架构经验
- ✅ **大厂 Java 受众覆盖** — agentcook 求职作品集对阿里/蚂蚁/字节系投递回复率不打折
- ✅ **DDD 教学完整** — 教程"产品架构师"高度上加一个核心案例
- ✅ **双后端协作真实** — Pact 契约 / gRPC / OpenAPI 全套企业级实践
- ✅ **第 33 讲 Harness Engineering 工程化** — agentcook = Python Harness + Java 业务后端,**完整解释为什么这么拆** — 教程价值再翻倍

### Negative
- ⚠️ 总周期 +5 day(30-45 → 35-50)
- ⚠️ 作者 sync +25-30%(60-110 → 75-130 分钟/天)
- ⚠️ 4 Agent 协作复杂度上升(冲突识别 / cross-cutting flag 多一个 owner)
- ⚠️ 维护成本 — 多一个 Java 仓库 + Maven + JPA + Spring 生态(长期成本)
- ⚠️ 部署成本 — K8s 多一个 Java 服务,资源消耗 ~512MB-1GB RAM

### Risk
- ❗ Agent D 与 A 在 Day 24 API spec 冻结时**协作高峰**,若 spec 设计有缺陷会双向返工
- ❗ Python 主壳 + Java 业务后端**通信延迟**(gRPC 跨进程),需 Phase 4 性能测试验证
- ❗ Phoenix 真实代码脱敏到 agentcook-java **不能直接 copy**,要重写 + 严格法务自检(详 desensitization-feasibility.md)

## Alternatives Considered

| 方案 | 否决理由 |
|---|---|
| ✅ **B 全量 — 加 agentcook-java(本 ADR)** | 选 |
| ❌ A 改教程对齐工程(03/04/06 砍 Java) | 教程稳态有 risk + Java 受众丢失 + 企业级高度被砍 |
| ❌ C 写 ADR 声明 "v1 只 Python,v1.5 加 Java" | v1 未兑现教程承诺,读者会失望 6-12 个月 |
| ❌ D Phase 2 末再决定 | 决策不一致 gap 拖 30+ 天 |
| ❌ Kotlin + Spring 替代 Java | 团队 Java 背景(P7 用户),教程已写 Java,无需切换 |

## Implementation

### Phase 1 末(Day 15)
- 作者 review 本 ADR + agent-d-java-architect.md
- 不动 Phase 1 任务,仅文档收敛

### Phase 2 (Day 16-25)
- Day 16-17:Agent D 启动,Spring Boot 3 + Maven workspace + DDD 4 模块 skeleton
- Day 18-20:Agent D 写 DDD domain 层(5 个聚合)
- Day 21-23:Agent D 写 application + infrastructure 层(JPA + Redis)
- Day 24:A 冻结 OpenAPI spec → D 用 openapi-generator 生成 Java DTO + Controller
- Day 25:Phase 2 review,Java 业务后端可独立跑 + Python 主壳通过 gRPC 调用

### Phase 3 (Day 26-37)
- D 完善 application 用例 + 双后端联调
- C 写 Pact contract for Java(consumer = admin/app,provider = Java)

### Phase 4 (Day 38-47)
- D + C 部署 Java app 到 K8s + Helm chart
- D + A swarm 协调(Java 注册到 etcd / Java 走 Traefik gateway)

### Phase 5 (Day 48-57)
- D 写 e2e 测试 + 性能测试 + 安全测试(JWT / OAuth / RBAC)
- D 写 Java 部分 README + DDD 教学文档(配套教程 03 讲深度参考)

## 与 v1.1+ 衍生品的关系

`final-deliverables-map.md` §5.5 提到的 "AI 协作开发主题" 现在升级 — agent-collab-templates 仓库要含 **4 Agent 协作 SOP**(原 3 Agent SOP 升级版),核心素材就是 integration-handbook.md 4 Agent 版本。

## References

- 教程 03/04/06 讲(原文)
- roadmap.md `## 二、技术选型`(原漏选 Java 处)
- ADR-001 Python 多包(本 ADR 不撤销 — Python 多包仍正确,只是补充 Java 业务后端)
- decisions-2026-05-19.md(本 ADR 落地的决策记录)
- phoenix-server(真实生产 Java DDD 工程,作者参与开发,脱敏后参考)
