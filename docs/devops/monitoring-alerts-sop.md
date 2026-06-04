# 监控告警 SOP(agentcook)

> **目标读者**:on-call 工程师 / SRE / 产品经理(看 LLM cost)。本文档对照 ADR-005 五维 observability,列出 Prometheus / Grafana / Langfuse / OTel 在 agentcook 的真配置 + 7 关键告警阈值 + on-call 升级路径 + 复盘模板。
>
> **配套**:
>
> - `k8s-operations-manual.md`(运维操作)
> - `troubleshooting-runbook.md`(5 故障诊断)
> - ADR-005 Observability stack
> - Day 50 perf report(p95 1900ms / p99 2300ms / 38K token / 76% 预算 baseline)

---

## 1. 五维 observability 速览(对照 ADR-005)

| 维度         | 工具                       | 路径 / 端口                                                            | 用途                           |
| ------------ | -------------------------- | ---------------------------------------------------------------------- | ------------------------------ |
| **Trace**    | OpenTelemetry SDK + Jaeger | `otel-collector:4317`(gRPC OTLP)                                       | 端到端调用链 / 异常 span 反查  |
| **Metrics**  | Prometheus + Grafana       | scrape `:8889`(otel-collector)+ 服务 `/metrics` `/actuator/prometheus` | QPS / 延迟 / 错误率            |
| **Logs**     | structlog + slf4j → Loki   | container stdout(JSON 结构化)                                          | 全文检索 / 关联 trace ID       |
| **LLM 专属** | Langfuse                   | https://cloud.langfuse.com                                             | Prompt 版本 / Trace / 成本分析 |
| **业务看板** | 自建 Grafana dashboard     | `agentcook · Overview` 等 3 个                                         | Agent 完成率 / 用户留存        |

---

## 2. Prometheus 配置(scrape targets)

`agentcook-swarm/observability/prometheus.yml`(staging compose)+ K8s `kube-prometheus-stack` ServiceMonitor(prod):

| job_name       | target                | path                   | 用途                                                      |
| -------------- | --------------------- | ---------------------- | --------------------------------------------------------- |
| otel-collector | `otel-collector:8889` | `/metrics`             | OTel SDK 推上来的所有 instrument                          |
| agent-core     | `agent-core:8000`     | `/metrics`             | Python `prometheus_client`(http*requests_total / chat*\*) |
| connector      | `connector:8082`      | `/metrics`             | Python connector 端                                       |
| admin-bff      | `admin-bff:8080`      | `/actuator/prometheus` | Spring micrometer(http*server_requests_seconds*\*)        |

**全局参数**:`scrape_interval: 15s` / `evaluation_interval: 15s`(默认)。

**retention(prod)**:`--storage.tsdb.retention.time=30d` + 每周看一次磁盘(`/prometheus`)。

---

## 3. 4 Grafana Dashboards 速查

> Day 62 加第 4 个 `Security & Rate Limit`(`security-rate-limit.json`),覆盖 Phase 5 backlog #11 落地后的边缘 + 应用层防护可视化。Day 55 之前 brief 一直说"4 dashboards"是脑补,Day 62 真补齐。

### 3.1 `agentcook · Overview`

| 面板                     | promql                                                                                   | 用途     |
| ------------------------ | ---------------------------------------------------------------------------------------- | -------- |
| Total Requests (last 5m) | `sum(rate(http_requests_total[5m]))`                                                     | QPS 总览 |
| Error Rate (5xx)         | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` | 5xx 占比 |
| p95 latency              | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`  | 性能基线 |
| p99 latency              | `histogram_quantile(0.99, ...)`                                                          | 长尾监控 |
| Request rate by service  | per `service` 维度                                                                       | 流量分布 |
| Status-code distribution | 200 / 4xx / 5xx 堆叠                                                                     | 错误占比 |
| Recent error logs        | Loki query `{severity="error"}`                                                          | 关联日志 |

### 3.2 `agentcook · Service Health`

| 面板                                | 用途                                               |
| ----------------------------------- | -------------------------------------------------- |
| Services up / down                  | `up{job=~"agent-core\|admin-bff\|connector"}` 心跳 |
| Service status                      | 综合健康度                                         |
| CPU usage by container (% of limit) | container 级 CPU 使用                              |
| Memory (RSS, MB)                    | container 级 RSS(配 OOM 预警)                      |
| gRPC inbound rate                   | `grpc_server_started_total`                        |
| gRPC error rate by method           | per method 错误率(找哪个 RPC 异常)                 |
| Service errors / warnings           | 跨服务异常事件流                                   |

### 3.3 `agentcook · LLM Metrics`(成本敏感)

| 面板                          | 用途                                                        |
| ----------------------------- | ----------------------------------------------------------- |
| Total LLM calls (last 24h)    | 调用量趋势                                                  |
| Tokens in / out (last 24h)    | token 消耗(关联 cost)                                       |
| Estimated cost USD (last 24h) | **预算监控** — 与 Day 50 baseline(38K token / 76% 预算)对照 |
| Calls/min by model            | qwen-turbo / qwen-plus / echo 占比(fallback 是否触发)       |
| p95 LLM latency by provider   | qwen 上游延迟(Day 50 §4 瓶颈 #3 监控)                       |
| Top 10 longest recent calls   | 找异常长 call(可能是 timeout 边界)                          |

### 3.4 `agentcook · Security & Rate Limit`(Day 62 加 / 9 panel)

| 面板                                       | 用途                                                |
| ------------------------------------------ | --------------------------------------------------- |
| Turnstile 验证失败率(5min)                 | 阈值 > 30% 触发 alert(R1 缓解信号)                  |
| Rate Limit 命中数(5min)                    | 429 突增信号                                        |
| Turnstile pass / fail 趋势                 | 1m rate 二维曲线                                    |
| Rate Limit 429 by service                  | 哪个 service 被刷最多(chat / login / API)           |
| Top 10 被限速 IP(1h)                       | 反黑名单参考                                        |
| chat /api/v1/chat/stream 状态码分布        | 200 / 401 / 429 / 5xx 看比                          |
| Cloudflare Worker turnstile-verify(call/s) | 边缘验证调用量(需 Cloudflare exporter)              |
| Cloudflare Worker rate-limit(call/s)       | 边缘 throttle 量                                    |
| K8s ingress 兜底 throttle(daily)           | Cloudflare 全挂时 K8s nginx-ingress fallback 触发量 |

---

## 4. 9 关键告警阈值(Day 62 +2 turnstile/rate-limit)

每条 alert 在 `deploy/helm/agentcook/templates/prometheusrule.yaml`(Day 53 C 已落)有真定义。Grafana UnifiedAlerting 通过 Prometheus 数据源自动 sync 这些 rule(避免重复定义);Grafana 这一侧只配 receiver + routing(`agentcook-swarm/grafana/provisioning/alerting/`,Day 55 C)。

| #   | alert name(prometheusrule.yaml)    | 告警                 | 阈值                            | 严重度         | 联动                                       |
| --- | ---------------------------------- | -------------------- | ------------------------------- | -------------- | ------------------------------------------ |
| 1   | `AgentcookHTTP5xxSpike`            | HTTP 5xx 突增        | > 1% 持续 5m                    | 🔴 P1 critical | runbook §6 / Grafana critical channel      |
| 2   | `AgentcookP99LatencyDegraded`      | p99 latency 退化     | > 2.5s 持续 10m(基线 2.3s +10%) | 🟡 P2 warning  | Day 50 perf 对照 / Grafana default channel |
| 3   | `AgentcookPodRestartingFrequently` | Pod 重启             | > 3 次/15min                    | 🔴 P1 critical | runbook §1-2 / Grafana critical channel    |
| 4   | `AgentcookPodOOMKilled`            | OOM kill             | ≥ 1 次/15min                    | 🔴 P1 critical | runbook §2 + §5 / Grafana critical channel |
| 5   | `AgentcookCPUHigh`                 | CPU 持续 > 80% limit | > 0.8 持续 10m                  | 🟡 P2 warning  | HPA 应自动扩,见 runbook §8                 |
| 6   | `AgentcookLLMTokenCostSpike`       | Token cost 突增      | > $50/24h(可调)                 | 🟡 P2 warning  | 切 fallback / Grafana llm-cost channel     |
| 7   | `AgentcookChatFailRateHigh`        | chat fail rate       | > 5% 持续 10m                   | 🔴 P1 critical | runbook §6 / Grafana critical channel      |
| 8   | `AgentcookTurnstileFailRateHigh`   | Turnstile 验证失败率 | > 30% 持续 5m                   | 🟡 P2 warning  | runbook §10 / Grafana default channel      |
| 9   | `AgentcookRateLimitHitSpike`       | rate-limit 命中突增  | > 100 次/min 持续 5m            | 🟡 P2 warning  | runbook §11 / Grafana default channel      |

**完整 promql 见 `deploy/helm/agentcook/templates/prometheusrule.yaml`**(每条带 runbook_url 链回本项目)。

### 4.1 落地状态(Day 55 C 校准)

- ✅ `deploy/helm/agentcook/templates/prometheusrule.yaml`(100+ 行 / 1 资源 / 3 group / **9 alerts** — Day 53 落 7 + Day 62 加 Turnstile + RateLimit 2 个)
- ✅ `agentcook-swarm/grafana/provisioning/alerting/contact-points.yml`(3 receiver:default / critical / llm-cost)— Day 55 C 落
- ✅ `agentcook-swarm/grafana/provisioning/alerting/notification-policies.yml`(severity-based routing)— Day 55 C 落
- 📅 真 webhook URL(Slack / 钉钉 robot URL)填入 Grafana env var:`GRAFANA_WEBHOOK_URL_DEFAULT/CRITICAL/LLM_COST` — 留作者首发后填,Phase 5 buffer
- 📅 cluster 真装 kube-prometheus-stack(prod 实跑)— Phase 5 backlog,首发后

**重复定义防御**:Grafana UnifiedAlerting 通过 Prometheus 数据源自动 sync alert,**不在 Grafana 这边重复写 alert rule** — Prometheus rules 是单一来源。Grafana 只管路由 + 通知通道。

---

## 5. Langfuse cost 告警(LLM 专属)

Langfuse 是 LLM 调用专属的可观测性平台 — agentcook 的 chat 走 qwen 真栈,token 消耗由 Langfuse 统一计量。

### 5.1 当前接入

- `agentcook/src/agentcook_app/llm/observability.py`(A Day 41-43 落)— `@observe` 装饰器自动 trace 每次 chat
- 关键字段:`prompt_tokens` / `completion_tokens` / `total_cost_usd` / `model` / `latency_ms`
- 项目维度:Langfuse `project_id=agentcook-prod` 与 `agentcook-staging` 分开

### 5.2 cost 监控基线(Day 50 实测)

| 场景                       | token / call | cost USD / call | 月预算占比(假设 1K calls/day) |
| -------------------------- | -----------: | --------------: | ----------------------------- |
| 100u baseline(qwen-turbo)  |           38 |        0.000076 | ~7.6% / 月                    |
| 单 chat 长对话(8K context) |        ~9000 |           0.018 | 50% 月                        |

### 5.3 告警规则(Langfuse 自带 alerts UI)

1. **日 cost > $10** → Slack notify
2. **单 user 日 cost > $1** → 触发 ADR-018 配额降级(qwen-turbo → glm-4-flash,Day 53-54 协调员起草)
3. **单 call latency > 5s** → 触发 fallback chain(qwen-turbo → qwen-plus → echo)

---

## 6. on-call SOP

### 6.1 分级响应

| 级别              | 触发                                      | 响应时间 | 处理                                           |
| ----------------- | ----------------------------------------- | -------- | ---------------------------------------------- |
| **P0** 服务全挂   | demo.agentcook.cc 5xx > 50% / 全 pod down | 5 min    | runbook §9 紧急恢复 + Cloudflare DNS 切回 blue |
| **P1** 主链路异常 | chat fail > 5% / pod 反复重启             | 15 min   | runbook §6 chat 5xx / §1 CrashLoop             |
| **P2** 性能退化   | p99 > 阈值 / CPU > 80%                    | 1 h      | Day 50 perf 对照 / HPA 扩容                    |
| **P3** 单点告警   | 单 pod 告警 / cost 略超                   | 4 h      | 例行排查                                       |

### 6.2 升级路径

```
P0/P1 触发 → 当值 on-call(立即响应)
       ↓ 30min 内未恢复
       → 副 on-call + Tech Lead
       ↓ 1h 内未恢复
       → 全员通告 + 启动事件指挥
```

### 6.3 复盘模板(每个 P0/P1 事件必做)

```markdown
# Incident Report — YYYY-MM-DD HH:MM

## 概述

- 严重度:P0 / P1
- 持续时长:HH:MM ~ HH:MM(共 X 分钟)
- 影响:具体服务 / 用户数 / 错误数

## 时间线(精确到分钟)

- HH:MM 告警触发
- HH:MM on-call 响应
- HH:MM 定位根因
- HH:MM 修复完成
- HH:MM 验证恢复

## 根因

- 直接原因:
- 根本原因(为什么)1-3 层 5-Why:

## 修复

- 立即修复:
- 长期修复:

## 改进项

- [ ] 加 alerting 防同款再发
- [ ] 更新 troubleshooting-runbook.md 加新场景
- [ ] 修代码 / 配置 / 流程
```

---

## 7. 与 ADR / 其他文档的引用关系

| 来源                     | 内容                                             |
| ------------------------ | ------------------------------------------------ |
| ADR-005                  | 5 维 observability 决策                          |
| ADR-006                  | Blue-Green 策略(切流量监控点)                    |
| Day 50 perf report       | p95/p99 latency baseline / token cost / 3 大瓶颈 |
| Day 51 compliance report | A09 已确认 OTel + Langfuse + Prom 全 wired ✅    |

---

## 8. Day 53-54 C 待补 backlog

- [ ] `deploy/helm/agentcook/templates/prometheusrule.yaml`(9 alerts 真落)
- [ ] AlertManager → Slack / 钉钉 webhook 接入
- [ ] Loki promtail sidecar(Phase 5 buffer)
- [ ] Grafana 4th dashboard `Business Funnel`(Agent 完成率 / 用户留存 / 转化漏斗,ADR-005 业务看板)

---

**最后更新**:2026-06-03 · Phase 5 Day 52 · Agent C
**配套**:`k8s-operations-manual.md` / `troubleshooting-runbook.md` / `production-configuration.md`(Day 53-54 续)
