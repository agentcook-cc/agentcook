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

## 快速开始

```bash
# 安装主应用
pip install agentcook

# 启动服务
uvicorn agentcook:app --host 0.0.0.0 --port 8000
```

## 配套教程

《从 0 到 1 构建商业级 AI Agent 产品》

## 项目最终愿景

完整愿景与全景(6 大类产出物 + 4 使用场景 + 时间线 + 价值杠杆图)见配套教程仓库:

`build-ai-agent-product/tutorial/_internal/L3-strategy/final-deliverables-map.md`

> 简短:agentcook 是一份**开源 Agent Harness** + **完整的"产品架构师"教程** + **简历级求职作品集** + **中国大陆开发者环境配置工具书** —— 5 个独立可用的产物互相杠杆放大,长期持有。

## License

MIT © 2026 agentcook contributors
