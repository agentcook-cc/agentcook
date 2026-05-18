# ADR-012: agentcook 定位为开源 Agent Harness(叙事升级)

## Status

Accepted (2026-05-17)

## Context

**Harness Engineering** 是 Anthropic 推广的新工程学科,指**模型之上、把 LLM 变成可在生产环境长时运行 Agent 所需的整套工程脚手架** — 不是模型本身,不是 prompt 工程,不是 fine-tuning,是**模型上面的运行时框架**。

Harness 涵盖 9 个子问题:
1. Agent Loop(read → plan → act → observe → repeat)
2. Tool Use 调度(注册 / 并行 / 错误恢复)
3. System Prompt 管理(分段 + prefix-cache 友好)
4. Context Management(Compaction / Pruning / 召回)
5. Sub-agent 编排(父子通信 / 委派)
6. Memory(跨会话 / Identity / Soul / Diary)
7. Safety / Sandboxing(工具沙箱 / prompt 注入防御)
8. Observability(trace / token / 失败诊断)
9. Cost Optimization(模型路由 / cache / context 窗口)

**关键洞察**:agentcook 一直在做 harness engineering,只是没用这个名字。回顾资产:

- `agentcook-core` 9 模块全部是 harness 的子组件
- 11 份 ADR(001-011)几乎每一条都是 harness 设计决策
- Phase 1-5 70 天工作本质就是在实现一个完整 harness

**问题**:之前对外叙事是"AI Agent 产品教程",这低估了项目高度。"Agent 产品"是结果,"Agent Harness"才是方法论 — 后者卖点硬数量级:
- **简历价值**:"开发了开源 Agent Harness"硬过"做了一个 AI Agent 产品",直接对标 Devin / Claude Code / Manus
- **教程独特性**:中文世界几乎没有 "Harness Engineering" 实战指南
- **传播话题度**:2026 年 harness engineering 是 AI 工程圈热点
- **求职面试**:能讲清"我做的 9 个 harness 维度怎么设计"的人,在面试里完全不同档次

## Decision

### 1. agentcook 显式定位升级

| 维度 | v1 叙事(2026-05 前) | v2 叙事(本 ADR 起) |
|---|---|---|
| 项目 tagline | 商业级 AI Agent 产品完整技术栈 | 开源 Agent Harness + Harness Engineering 实战 |
| 教程定位 | AI Agent 产品教程 | Harness Engineering 实战指南(基于真实生产 harness 设计经验) |
| README 第一段 | 强调"商业级 + 完整技术栈" | 强调"open-source Agent Harness + 9 harness 维度全覆盖" |
| 简历卡位 | AI Agent 产品研发 | 开源 Agent Harness 框架作者 |
| 系列 Slogan(保留不动) | 半个月,大厂 P7 教会你从 0 到 1 上线一款 AI Agent 产品(附开源) | **不变** — 普通读者的吸引力 + 不引入"harness"术语认知负担 |

**关键:对外叙事双轨**:
- **大众层**(Slogan / 微信公众号 / 掘金主标题):用"AI Agent 产品" — 普通开发者一眼懂
- **专业层**(README / ADR / 技术博客 / Hacker News / 简历):用"Open-source Agent Harness" — 同行 / 面试官识别高度

### 2. 9 harness 维度 ↔ 11 ADR ↔ agentcook 模块对照

| Harness 子问题 | agentcook 实现 | 相关 ADR |
|---|---|---|
| 1. Agent Loop | `agentcook-core` Agent 抽象 + LangGraph 编译 | ADR-001 / 002 |
| 2. Tool Use 调度 | Tool / Plugin / Skill protocol | ADR-001 / 004 |
| 3. System Prompt 管理 | Identity / Soul prefix-cache 友好注入 | ADR-011 |
| 4. Context Management | `compaction` + `pruning` 模块(Phase 2 Day 22) | ADR-011 |
| 5. Sub-agent 编排 | `multi_agent` 模块(LangGraph 声明式 router) | ADR-002 |
| 6. Memory | Identity / Soul / Memory / Diary 四层栈 | ADR-011 |
| 7. Safety / Sandboxing | Plugin Docker 沙箱 + 攻击向量测试 | ADR-004 |
| 8. Observability | OpenTelemetry + Jaeger + Prometheus + Langfuse | ADR-005 |
| 9. Cost Optimization | `model_router` + prefix-cache 利用 | ADR-002 / 011 |

**9/9 全覆盖**。agentcook 是一份完整的 harness 实现。

### 3. 业界对照(教程 + 求职用)

| Harness 实现 | 出品方 | 开闭源 | 与 agentcook 关系 |
|---|---|---|---|
| **Claude Code** | Anthropic | 闭源(部分模式可见) | reference,我们借鉴模式(尤其 system prompt 分段 / context compaction) |
| **Devin** | Cognition | 闭源 SaaS | 商业 harness 标杆,定位天花板高 |
| **Manus** | Manus AI | 闭源 SaaS | 同上 |
| **LangGraph** | LangChain | 开源 | multi-agent 引擎,**我们的依赖**(ADR-002) |
| **Mastra** | Mastra Labs | 开源 TS Agent 框架 | **最接近的竞品** — Mastra 是 TS,我们是 Python;Mastra 偏框架,我们偏教学+框架双轨 |
| BabyAGI / AutoGPT | OSS 社区 | 开源,基本停滞 | 第一代,我们超越 |

**agentcook 差异化定位**:
- **完整 harness**(9 维度全覆盖,大多数 OSS 只覆盖 4-6 个)
- **Python 生态**(开源 Python harness 几乎只有 LangGraph,但 LangGraph 是引擎不是完整 harness)
- **教程配套**(教读者*如何做 harness engineering*,不只是给一个工具用)
- **真实生产经验脱敏**(基于阿里生产 PC Agent 工程的 gap 分析与借鉴)

### 4. 教程章节增量

Phase 5 末新增**第 33 讲《Harness Engineering 工程化》**(预留,Phase 5 实际写时再 finalize):
- 介绍 harness engineering 学科 + 9 维度
- 12 ADR 按 9 harness 维度重新编排讲解
- 业界 harness 对照(Claude Code / Devin / Manus / LangGraph / Mastra)
- 给读者一份"自己设计 harness 的 checklist"

### 5. README + PROMPT.md 叙事改动

详见本 ADR commit 配套修改。

### 6. 教程内容稳定区不动

32 讲教程主体(`tutorial/chapters/01-29`)**不重写** — 已稳态(15994 行 / 杜撰已清零)。只在:
- 主入口(README / PROMPT.md / 教程首页)注入 harness 叙事
- Phase 5 末新增第 33 讲补完 harness engineering 专题
- 适当地方(eg. chapters/README.md 总目录)加"本系列实际上是一份 Harness Engineering 实战指南"卡位

不对已稳定章节做大改 — 风险高 + 价值低。

## Consequences

### Positive
- ✅ 叙事高度提升 — 从"做了个 Agent 产品" → "开源 Agent Harness + Harness Engineering 实战指南",传播 / 简历 / 教程独特性全方位升级
- ✅ **不需要新工程量** — 纯叙事 + 加 1 个 ADR + 加 1 个章节预留,Phase 1-5 工程不变
- ✅ 11 ADR 体系自然形成"Harness Engineering 实践清单",方法论高度提升
- ✅ 对标 Claude Code / Devin 而不是 LangChain demo,定位天花板更高
- ✅ 求职面试时可直接说"我做了一个开源 Agent Harness,9 个 harness 维度全覆盖,12 份 ADR" — 数量级超过"做了个 Agent 产品"
- ✅ 双轨叙事保留 Slogan 大众吸引力(不损失普通读者)

### Negative
- ⚠️ "Harness Engineering" 这个术语在中文世界还不普及 — 需要在 README / 教程首页 / 博客显式解释"什么是 harness"
- ⚠️ 部分读者可能觉得"叫法太洋气"反感 — 双轨叙事(Slogan 保留)缓解
- ⚠️ 若业界 2027 年降温该术语,叙事会显过时(风险中等)
- ⚠️ "harness" 一词有歧义(test harness / wire harness)— 教程首讲必须明确定义

### Risk
- ❗ 若 harness engineering 术语在英文世界都未沉淀,中文圈推广更难 → 持续监控 Anthropic / Devin / Manus 的官方使用频率
- ❗ 同义 harness 用法混淆 — 教程 / README 首句必须澄清"这里 harness 特指 Anthropic 定义的 Agent harness"

## Alternatives Considered

| 方案 | 否决理由 |
|---|---|
| 不升级叙事,保持"Agent 产品"定位 | 错过高 leverage 叙事机会,简历价值低 |
| 用"Agent 框架"而不是"Agent Harness" | "框架"太宽泛,harness 更精准 + 更新颖 + 直接对应业界讨论 |
| 用"LLM OS"(Karpathy 用法) | LLM OS 偏长期愿景,harness 是 2026 年可落地的工程实践,更接地气 |
| 大改教程章节内容统一叙事 | 教程已稳态(杜撰清零),改动风险高 |
| 全面切到"harness"术语,放弃 Slogan | 损失普通读者,得不偿失;双轨叙事最优 |

## Implementation

### 2026-05-17(本 ADR 写完即做)
- 写本 ADR(`ADR-012-agent-harness-philosophy.md`)
- 改 `agentcook-cc/README.md` 顶部叙事
- 改 `tutorial/PROMPT.md` 顶部叙事升级段
- 加 `chapter-ownership.md` Phase 5 新增章节预留
- 同步索引(v6-architecture-rationale.md / master-execution-plan.md / phase1-launch-sop.md / agent-a-architect.md / integration-brief-day-6.md / gap 报告)

### Phase 5 末(Day 56-57)
- Agent A / 作者协作写第 33 讲《Harness Engineering 工程化》
- 章节登记表加正式行

### 教程首发博客(上线后)
- 第一发破圈博客双语 hook:中文标题用 Slogan,副标题/英文 tagline 强调 "Open-source Agent Harness"
- Hacker News / dev.to 投递用英文 harness 定位(国际同行识别度高)

## References

- Anthropic 关于 Claude Code 的 harness 实践公开文章(2025-2026 年陆续发布)
- Karpathy "LLM OS" 演讲(2024)— 相关但更长期的概念
- 该真实工程 PE(phoenix-engine)gap 分析(`../adr-vs-phoenix-pc-gap-analysis.md`)— 印证 harness 9 维度的完整性
- 配套实施:tutorial Phase 5 末新增第 33 讲《Harness Engineering 工程化》
