# ADR-005: 完整 Observability 栈（OpenTelemetry + Langfuse）

## Status

Accepted (2026-05-16)

## Context

Agent 类产品具有高度不确定性：LLM 响应非确定性、多步编排链路复杂、Plugin 执行可能失败。仅依赖 Cloudflare Analytics 的页面浏览量统计远不足以支撑生产级运维需求。

缺乏以下关键可观测能力：
- 端到端调用链追踪（哪一步耗时最长？）
- LLM Token 消耗与成本核算
- Plugin 执行错误率与异常堆栈
- 业务指标（Agent 完成率、用户满意度）

## Decision

构建五维 Observability 体系：

| 维度 | 技术选型 | 用途 |
|------|----------|------|
| **调用链** | OpenTelemetry SDK + Jaeger | 分布式 Trace，定位性能瓶颈 |
| **指标** | Prometheus + Grafana | QPS、延迟、错误率、Token 消耗 |
| **日志** | structlog + Loki | 结构化日志，支持全文检索 |
| **LLM 专属** | Langfuse | Prompt 版本管理、Trace 可视化、成本分析 |
| **业务看板** | 自建 Dashboard | Agent 完成率、用户留存、转化漏斗 |

### 部署策略
- **本地开发**：Docker Compose 默认集成 Jaeger + Loki + Langfuse，一键启动
- **K8s 生产**：通过 Helm chart 的 `values.yaml` 选择性启用各组件，支持水平扩展

### 双链路设计
- **Dev Trace**：技术视角，记录每个节点的输入输出、耗时、异常
- **Biz Trace**：业务视角，关联用户 ID、会话 ID、最终结果，用于产品分析

## Consequences

### Positive
- **生产级可观测**：满足 SRE 标准的监控告警与故障排查能力
- **双链路互补**：技术人员查 Dev Trace 定位 bug，产品经理看 Biz Trace 分析转化

### Negative
- **基础设施复杂度增加**：新增 5 个中间件组件，运维负担加重
- **本地开发资源占用**：Jaeger + Loki + Langfuse 全量启动需占用 ~2GB 内存，低配机器可能卡顿
