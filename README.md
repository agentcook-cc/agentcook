# agentcook

**Open-source Agent Harness** — 9 harness 维度全覆盖的生产级 AI Agent 运行时框架。

> 配套教程《从 0 到 1 构建商业级 AI Agent 产品》,半个月教你从 0 到 1 上线一款 AI Agent 产品(附完整开源工程)。

## 什么是 Agent Harness?

**Harness** 是 Anthropic 推广的术语,指**模型之上、把 LLM 变成可在生产环境长时运行 Agent 所需的整套工程脚手架** — 不是模型,不是 prompt,是**模型上面的运行时框架**。Claude Code 自己就是 Anthropic 的 reference harness。

agentcook 实现完整 9 harness 维度:

| # | Harness 维度 | agentcook 实现 |
|---|---|---|
| 1 | Agent Loop | `agentcook-core` + LangGraph |
| 2 | Tool Use 调度 | Tool / Plugin / Skill protocol |
| 3 | System Prompt 管理 | prefix-cache 友好分段 |
| 4 | Context Management | compaction + pruning |
| 5 | Sub-agent 编排 | LangGraph 声明式 router |
| 6 | Memory | Identity / Soul / Memory / Diary 四层 |
| 7 | Safety / Sandboxing | Plugin Docker 沙箱 |
| 8 | Observability | OpenTelemetry + Langfuse |
| 9 | Cost Optimization | model_router + cache |

完整设计决策见 [docs/adr/](docs/adr/)(12 ADR)。

## 仓库矩阵

| 包 | 说明 | 类比 | 状态 |
|---|---|---|---|
| agentcook-core | Agent 抽象层 + Plugin Bundle 接口 + 9 模块 protocol | langchain-core | 开发中 |
| agentcook-providers | LLM Provider 适配层 (OpenAI/Anthropic/Qwen/Zhipu) | langchain-openai | 开发中 |
| agentcook-storage | 存储抽象层 (PostgreSQL + pgvector / Redis / S3) | - | 开发中(Phase 2 Day 17 起,详 ADR-011) |
| agentcook | FastAPI 主应用，编排 core + providers + storage | - | 开发中 |
| agentcook-admin | Vue 3 + Element Plus + TypeScript 管理端 | mall-admin-web | 开发中 |
| agentcook-app | React + Tailwind + shadcn/ui + Electron 用户端 | - | 开发中 |
| agentcook-swarm | 微服务版 (gateway/agent/skills/connector/admin) | mall-swarm | 规划中 |
| agentcook-design-tokens | 共享设计系统 token | - | 开发中 |
| agentcook-starter | 教学最小集 (545 行核心逻辑) | mall-tiny | 开发中 |
| **agentcook-java** ★ | **Java 17 + Spring Boot 3 + DDD 四层** (api/application/domain/infrastructure) + 5 domain 聚合 + gRPC 调 Python 主壳 | mall-business | 开发中(Phase 2 Day 16 起,详 ADR-013) |
| docs | ADR 架构决策记录 + 架构文档 | - | 维护中 |

## 开发者快速上手

### 前置条件

- Python 3.11+、[uv](https://docs.astral.sh/uv/) 包管理器
- Java 17+、Maven Wrapper（`./mvnw`，已内置）
- Docker（推荐 colima）+ docker compose v2
- Node.js 20+、pnpm 9+

### 一键启动

```bash
# 1. 安装 Python 依赖
uv sync --group dev

# 2. 启动全部服务（docker-compose + Python app）
make dev

# 单独启动 docker 中间件（不启动 app）
make dev-infra   # 等同于 docker compose up -d
```

### 跨 repo git hooks（Phase 6 #28）

本仓库与作者的 `agentcook` 工作区仓平行存放（兄弟目录）。提交源码到本仓时，常常忘记把对应的 `audit/` / `progress/` 笔记 commit 到工作区仓 — 协调员 review 时看到代码已 push 但找不到对应文档（cookbook 23 子项 #22 累计教训 4 次）。

仓库自带一个 `.githooks/pre-push` 守门员：检测到工作区仓的 `tutorial/_internal/audit/` 或 `tutorial/_internal/progress/` 有未提交的新文件时阻止 push。

一次性启用（每个 clone 执行一次）：

```bash
git config core.hooksPath .githooks
```

故意绕过（明确就是想先推源码、稍后补文档）：

```bash
git push --no-verify
```

### 常用命令（Makefile）

```bash
make help          # 查看所有命令
make dev           # 启动 docker-compose + Python app（:8000）
make test-py       # Python 全量测试
make test-py-unit  # 仅 unit 测试（不需要 Docker）
make test-py-cov   # 测试 + 覆盖率报告
make test-java     # Java 全量测试
make lint          # Python ruff check + format check
make ci-local      # 本地模拟完整 CI
make down          # 停止 docker-compose
make clean         # 停止 + 清除 volumes
```

### 端口一览

| 服务 | 端口 | 说明 |
|------|------|------|
| agentcook Python | 8000 | FastAPI runtime |
| agentcook Java | 8080 | Spring Boot（Phase 2 Day 22+） |
| PostgreSQL (pgvector) | 5432 | 应用数据库 |
| Redis | 6379 | 缓存 + 会话 |
| Pact Broker | 9292 | 契约测试 |
| Jaeger UI | 16686 | 链路追踪 |
| Prometheus | 9090 | 指标监控 |
| admin (Vue) | 5173 | 管理端 dev server |
| app (React) | 5174 | 用户端 dev server |

## 配套教程

《从 0 到 1 构建商业级 AI Agent 产品》

## 项目最终愿景

完整愿景与全景(6 大类产出物 + 4 使用场景 + 时间线 + 价值杠杆图)见配套教程仓库:

`build-ai-agent-product/tutorial/_internal/L3-strategy/final-deliverables-map.md`

> 简短:agentcook 是一份**开源 Agent Harness** + **完整的"产品架构师"教程** + **简历级求职作品集** + **中国大陆开发者环境配置工具书** —— 5 个独立可用的产物互相杠杆放大,长期持有。

## License

MIT © 2026 agentcook contributors
