# ADR-006: Staging 环境 + Blue-Green 部署

**Status:** Accepted (2026-05-16)

## Context

当前直接部署到生产环境（prod）没有任何缓冲机制，一旦新版本出现严重问题，无法快速回滚，导致服务中断时间不可控。缺乏预发布验证环境，所有测试都在开发环境或本地进行，与生产环境差异较大，容易遗漏环境相关问题。

## Decision

采用 **3 环境梯度** + **Blue-Green 部署策略**：

### 环境梯度
- **dev**: localhost 本地开发环境
- **staging**: staging.agentcook.cc 预发布环境，用于 e2e 测试和集成验证
- **prod**: demo.agentcook.cc 生产环境

### Blue-Green 部署流程
1. 每次发版时启动新的 K8s Deployment（green 版本）
2. 在 green 版本上运行 e2e 测试和健康检查
3. 通过 Cloudflare DNS 将流量从 blue 切换到 green
4. blue 版本保留 24 小时，支持秒级回滚
5. 24 小时后清理旧的 blue 版本

## Consequences

### Good
- **零停机部署**：流量切换瞬间完成，用户无感知
- **秒级回滚**：出现问题时可立即切回 blue 版本
- **staging 可跑 e2e**：提供与生产一致的环境进行完整测试

### Bad
- **需双倍 K8s 资源**：部署期间需要同时运行两个版本，短暂增加资源消耗
- **部署复杂度增加**：需要维护 DNS 切换逻辑和健康检查机制
