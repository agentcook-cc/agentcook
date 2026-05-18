# ADR-001: Python 多包拆分（参考 LangChain 模式）

## Status

Accepted (2026-05-16)

## Context

当前项目采用单仓库 9 模块的架构设计，违反了关注点分离（Separation of Concerns, SoC）原则。随着功能迭代和模块增长，这种紧耦合的架构将导致后续重构成本急剧增加。

LangChain、LlamaIndex 等成熟的 AI Agent 框架已验证了多包拆分模式的有效性：用户可按需安装核心功能，测试矩阵清晰，发版流程独立可控。

## Decision

v1 版本将拆分为 4 个核心 Python 包，使用 uv workspace monorepo 进行统一管理：

| 包名 | 职责 |
|------|------|
| `agentcook-core` | 核心引擎、Agent 编排、状态管理 |
| `agentcook-providers` | LLM Provider、Connector 抽象与实现 |
| `agentcook-storage` | 记忆存储、向量数据库适配层 |
| `agentcook` | 元包，聚合以上三者提供完整能力 |

总计 11 个 GitHub 仓库矩阵：

| 仓库名 | 类型 | 说明 |
|--------|------|------|
| `agentcook-core` | Python 包 | 核心引擎 |
| `agentcook-providers` | Python 包 | Provider 层 |
| `agentcook-storage` | Python 包 | 存储层 |
| `agentcook` | Python 包 | 元包入口 |
| `agentcook-admin` | Web 应用 | 管理后台（Vue3 + Element Plus） |
| `agentcook-app` | Web 应用 | 用户前端（Next.js + shadcn/ui） |
| `agentcook-swarm` | Go 服务 | 分布式调度集群 |
| `agentcook-design-tokens` | 设计系统 | 共享 Design Tokens |
| `agentcook-starter` | 模板项目 | 快速启动模板 |
| `agentcook-docs` | 文档站点 | 官方文档 |
| `agentcook` | 主仓库 | Monorepo 根（uv workspace） |

## Consequences

### Positive
- **用户按需安装**：轻量级场景只需安装 `agentcook-core`，无需拉取全部依赖
- **测试矩阵清晰**：每个包的 CI/CD 可独立配置测试策略
- **发版独立**：核心引擎修复 bug 无需等待 storage 或 providers 发版

### Negative
- **Phase 1 开发成本增加**：包拆分、依赖声明、发布流水线预计多花 3-5 天
- **跨包调试复杂度**：本地开发需使用 `uv pip install -e` editable install 模式，调试链路变长

---

## v2 演进路径:Python 边界执行机制(Phase 2 起评估)

ADR-001 v1 解决"包怎么分",但**没解决"边界怎么强制不被破坏"**。Phase 2 起多 Agent 跨包 import 增多,需工具层加固。

**问题场景**:Agent A 写 `agentcook-core`,Agent B 写 `agentcook-providers`。假如 providers 直接 import `agentcook-storage` 的具体 PostgreSQL 实现绕过 core 抽象 → 包"形似多包,实是耦合一团",拆分意义归零。

### Python 三层边界执行

参考 TS 生态 `package.json exports + TS Project References + ESLint no-restricted-imports` 的三层联防,Python 等效方案:

| 层 | 工具 | 作用 |
|---|---|---|
| 1. 层级 import 限制 | `import-linter` + `grimp` | 配置文件声明"哪些包禁止 import 哪些包",违反则 CI 失败 |
| 2. 包边界隔离 | `pyproject.toml` 显式声明 `dependencies` + uv workspace 不允许跨包私自 import 未声明依赖 | 强制依赖关系可视化,新增依赖需 explicit |
| 3. CI 强制 | GitHub Actions 跑 `lint-imports` + `grimp graph --check`,失败 block merge | 不可绕过 |

### 示例配置(Phase 2 起草)

`.importlinter`:
```ini
[importlinter]
root_packages =
    agentcook_core
    agentcook_providers
    agentcook_storage
    agentcook

[importlinter:contract:1]
name = Providers cannot import storage internals
type = forbidden
source_modules = agentcook_providers
forbidden_modules = agentcook_storage.internal

[importlinter:contract:2]
name = Storage cannot import providers
type = forbidden
source_modules = agentcook_storage
forbidden_modules = agentcook_providers

[importlinter:contract:3]
name = Core cannot import any other agentcook package
type = forbidden
source_modules = agentcook_core
forbidden_modules =
    agentcook_providers
    agentcook_storage
    agentcook
```

### 实施时机

- **Phase 2 Day 17** Agent A 完成 `skill_loader` + `plugin_loader` 后启动评估
- 此时跨包 import 真正开始多,工具开销划算
- Phase 1 不上 — 单 Agent 主写 + 4 包 + 人脑能 hold,工具开销不值得

### 为什么不直接抄 TS 生态

Python 没有 TS Project References 这种语言内建机制,需要靠 lints 工具达到等效效果:
- `import-linter`(PyCQA 维护):社区最成熟的 Python 架构 lints 工具
- `grimp`:提供依赖图分析与可视化
- `uv workspace`:依赖声明强制可视化

参考:该真实工程 PE(phoenix-engine)在 TS 生态用 `package.json exports + Project References + ESLint no-restricted-imports` 三层联防,经过生产验证。我们采纳同样的"三层联防"哲学,工具替换为 Python 等效物。
