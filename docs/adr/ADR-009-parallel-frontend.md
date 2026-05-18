# ADR-009: Admin + App 部分并行开发

**Status:** Accepted (2026-05-16)

## Context

当前开发流程采用强串行模式，admin 后台和 app 前端必须等待后端完全完成后才能开始开发，浪费了大量可并行的时间窗口。实际上两端大部分功能依赖的是稳定的 API 契约，而非具体实现细节。

## Decision

采用 **Phase 2 末尾冻结 API spec** + **Phase 3 并行开发** 策略：

### 关键时间节点
- **Phase 2 Day 25**：冻结 API spec
  - 输出 `API-CONTRACT-v1.md` 文档
  - 包含完整的 OpenAPI 规范（锁定版本）
  - 明确标注 deprecation 策略和迁移路径
- **Phase 3 启动**：admin + app 并行开发
  - admin 团队基于 API spec 开发后台管理界面
  - app 团队基于 API spec 开发用户端应用
  - 后端团队继续完善实现细节

### 前提条件
- API spec 必须真正冻结，后续变更需经过严格评审
- 建立 API 变更沟通机制，任何修改需同步通知两端团队
- 提供 Mock Server 供前端团队独立开发和测试

## Consequences

### Good
- **节省约 2 天开发时间**：并行开发缩短整体交付周期
- **两端可独立迭代**：admin 和 app 团队互不阻塞
- **提前发现 API 设计问题**：前端消费过程中暴露接口设计缺陷

### Bad
- **API 变更导致双端返工**：若 spec 冻结后仍需修改，两端都需调整
- **需强 freeze 纪律**：团队必须严格遵守 API 契约，避免随意变更
- **Mock Server 维护成本**：需要保持 Mock 数据与真实实现的一致性
