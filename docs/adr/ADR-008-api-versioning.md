# ADR-008: API 版本管理 + Deprecation Policy

**Status:** Accepted (2026-05-16)

## Context

当前 API 仅使用 `/api/v1/` 路径，没有明确的版本过渡策略。当需要引入不兼容的 API 变更时，缺乏标准化的弃用和迁移机制，容易导致客户端断裂或被迫立即升级。

## Decision

采用 **URL Path Versioning** + **标准化 Deprecation Policy**：

### 版本化策略
- 使用 URL 路径区分版本：`/api/v1/` → `/api/v2/` → `/api/v3/`
- 每个版本独立维护，支持并行运行

### Deprecation Policy 时间线
以 v2 GA（General Availability）为基准：
1. **v2 GA 后 6 个月**：v1 标记为 deprecated
   - HTTP Response Header: `Deprecation: true`
   - OpenAPI 文档中标注 `deprecated: true`
   - 文档提供迁移路径说明
2. **v2 GA 后 12 个月**：v1 正式移除
   - 返回 `410 Gone` 状态码
   - 从代码库中删除 v1 相关实现

### 文档要求
- 每个 endpoint 在 OpenAPI 规范中明确标注 `deprecated: true`
- 提供详细的迁移指南，包括：
  - 变更点列表
  - 新旧参数对照表
  - 示例代码对比

## Consequences

### Good
- **向后兼容清晰**：客户端有充足的迁移窗口
- **迁移窗口充足**：6 个月警告期 + 6 个月过渡期
- **自动化标注**：OpenAPI 文档自动生成 deprecation 标识

### Bad
- **维护多版本 API 增加代码量**：需要同时维护多个版本的实现逻辑
- **路由复杂度增加**：需要管理不同版本的路由分发
