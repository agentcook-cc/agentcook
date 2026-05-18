# ADR-007: 4 层测试金字塔（含 Pact 契约测试）

**Status:** Accepted (2026-05-16)

## Context

当前只有单元测试和端到端测试，缺少契约测试层。在微服务架构下，服务间 API 变更缺乏保障，容易导致集成问题在生产环境爆发。前后端协作也缺乏自动化的接口一致性校验机制。

## Decision

采用 **4 层测试金字塔** 策略：

### 第 1 层：单元测试（Unit Tests）
- 工具：pytest（Python）、vitest（TypeScript）
- 覆盖率要求：≥80%
- 范围：单个函数、类、模块的逻辑验证

### 第 2 层：集成测试（Integration Tests）
- 工具：pytest + testcontainers
- 覆盖率要求：关键路径 100%
- 范围：数据库交互、外部服务调用、缓存操作等

### 第 3 层：契约测试（Contract Tests）
- 工具：Pact（pact-python + pact-js）
- 覆盖率要求：服务间 API 100%
- 角色定义：
  - **Consumer**: admin、app 前端应用
  - **Provider**: agentcook 后端服务
- 作用：自动校验前后端接口一致性，防止 API 变更破坏集成

### 第 4 层：端到端测试（E2E Tests）
- 工具：Playwright
- 范围：5 个核心用户流程
- 示例：用户登录 → 创建 Agent → 执行任务 → 查看结果 → 导出报告

## Consequences

### Good
- **微服务 API 变更有保障**：契约测试确保服务间接口兼容
- **前后端契约自动校验**：避免手动对接口的反复确认
- **测试层次清晰**：每层职责明确，便于维护和扩展

### Bad
- **Pact 学习成本**：团队需要掌握 Pact 的使用和维护
- **CI 时间增加**：4 层测试全部运行会延长构建时间
