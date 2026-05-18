# ADR-011: Agent 记忆体系与人格持久化

## Status

**Accepted** (2026-05-16,**2026-05-18 Day 9 Audit 提前 finalize**)

> **状态变更说明**(2026-05-18 晚,Day 9 audit 后修订):
>
> 提前 finalize 的**真实理由**是 **4 v1 默认决策成熟度足够**(基于 phoenix-engine gap 分析 + 业界 best practice),不是"代码已落地"。
>
> Day 9 audit 期间 Agent A grep 核实:**core/ 当前 6 protocol = Agent / Skill / Plugin / Connector / Tool / LLMProvider,Identity / Soul / MemoryStoreProtocol 实际 0 行代码**。Critical Finding CF-1 记录在 `_internal/audit/12-adr-landing-checklist.md` 与 `_internal/audit/decisions-2026-05-18.md` §11。
>
> **协调员失误声明**:Day 9 audit checklist 中"Phase 1 已经在用 IdentityProtocol/SoulProtocol/MemoryStoreProtocol"的描述是基于错误事实假设。决策成熟度判断仍正确,因此**不撤回 Accepted 状态**(撤回会让本就成熟的设计被质疑),但事实陈述必须诚实修订。
>
> **实际落地计划**:
> - Identity / Soul / MemoryStoreProtocol 接口 → Phase 2 Day 17 起 Agent A 写 storage 时补
> - 4 v1 默认决策(pgvector / hybrid / Auto Dream 关 / OpenAI 3-small) → Phase 2 Day 17-21 实施
> - Day 6-8 写的 6 个 protocol 是**前置基础**(Tool/Skill/Plugin 等),Memory 体系建在这之上
>
> Phase 2 实施时如需调整 v1 默认,走 ADR-011-v1.1 修订流程。

## Context

2026 年 Agent 产品的核心差异化之一是 **"记忆能力"**。无记忆的 Agent 用户体验类似无状态聊天机器人;有持久化记忆 + 稳定人格的 Agent 能跨会话、跨设备保留上下文,显著提升用户黏性与商业价值。

ADR-001 至 ADR-009 完成了"框架骨架"决策,但**一字未提记忆体系** — 这是个大洞,具体表现:
- `agentcook-core` 的 9 模块 protocol 没有 `MemoryStore` 抽象
- `agentcook-storage` 默认只规划了 PostgreSQL,没规划向量库
- System prompt 注入策略未定 → 影响 prefix-cache hit rate 与成本
- 用户对记忆的控制权(查看/编辑/删除)无产品形态

未做这套决策的代价:Phase 2 Agent A 写 `multi_agent` 时会被迫"临时拍脑袋"决定记忆怎么存,后期重构成本高;教程少一个"产品差异化"的大卖点章节。

参考:该真实工程 PE(phoenix-engine)有完整的 IDENTITY / SOUL / MEMORY / diary / Auto Dream / Memory Flush 设计经过生产验证,本 ADR 采纳其**层次结构哲学**,不复刻具体实现。

## Decision (Proposed)

### 四层记忆栈

| 层 | 用途 | 位置 | 可变性 |
|---|---|---|---|
| **1. Identity** | Agent 核心身份(name / role / 创建时间 / 用户授权范围) | `agentcook-core` 强抽象 | **不可变**(创建时锁定) |
| **2. Soul / Personality** | 性格倾向 / 语言风格 / 价值观 | `agentcook-storage` + `agentcook-core` 接口 | **稳定可调**(用户 explicit 修改) |
| **3. Memory** | 短期(会话内 KV)+ 长期(跨会话事件流)+ 语义(向量召回) | `agentcook-storage`(PostgreSQL + 向量库) | **持续累积** |
| **4. Diary / Reflection** | Agent 定期自我反思摘要,支撑长期人格演化 | `agentcook-storage` + 后台任务 | **生成型**(可禁用) |

### System Prompt 注入顺序(对 prefix-cache 友好)

```
[固定段 — 永不变,享受 prefix cache]
  Identity (创建时锁定)
  Soul (用户首次配置后稳定)
  System tools / Capabilities (版本相关)

[半固定段 — 缓存命中率较高]
  Memory 长期摘要(每日更新一次)

[动态段 — 每次请求计算]
  Memory 召回片段(按相关度 top-K)
  Current conversation
```

**关键**:Identity + Soul + 工具列表稳定不变 → 占满 prefix cache 的开头数千 token,显著降低 LLM 成本。Memory 召回必须放在动态段尾,不能污染固定段。

### 用户控制(隐私 + 信任)

- ✅ admin 提供"Memory 浏览器":用户可查看 Agent 关于自己的所有记忆,逐条编辑/删除
- ✅ "Memory Flush"按钮:重置 Memory 层但保留 Identity / Soul(给"我想重新开始"的用户)
- ✅ Identity / Soul 修改需要 explicit 二次确认(防 prompt injection 篡改人格)
- ✅ 用户 PII 进入 Memory 前需要明确告知(合规)

### v1 默认实现选择(2026-05-18 Day 9 Audit Accepted)

| 维度 | v1 决策 | 备选(v1.1+) | Audit 拍板理由 |
|---|---|---|---|
| 向量库 | ✅ **pgvector**(与 PostgreSQL 同库) | Qdrant / Chroma | 单库简化部署 + ADR-005 Observability 一体管理 + 中等规模(< 100 万 vectors)性能足够 |
| 召回算法 | ✅ **hybrid**(BM25 + embedding) | 纯 embedding similarity | hybrid 在中文场景胜过纯 embedding(关键词匹配补语义召回的盲区) |
| Auto Dream(后台反思) | ✅ **默认关,用户启用** | 默认开启 | 后台 LLM 调用增加成本 + 用户控制感 + 可作为"高级功能"卖点 |
| Embedding 模型 | ✅ **OpenAI text-embedding-3-small**(默认)+ 通义 / 智谱可选 | bge / m3e 本地模型 | 3-small 性价比最高($0.02 / 1M tokens),3 倍便宜过 ada-002;通义/智谱给国内用户备选 |

**v1.1+ 修订触发条件**:
- 向量数 > 100 万 → 评估迁移到 Qdrant / Chroma
- 中英文混合场景 hybrid 召回 precision < 0.7 → 评估纯 embedding 或 reranker
- 大量用户启用 Auto Dream + 反馈"反思有价值" → 评估默认开启
- OpenAI API 不可用区域 → 评估 bge 本地 embedding fallback

## Consequences

### Positive
- ✅ Agent 跨会话有连续性,用户体验大幅提升(2026 年用户对此期待已成默认)
- ✅ 教程多一个"产品差异化"卖点章节(《如何为 Agent 设计记忆与人格》)
- ✅ prefix-cache 友好的注入顺序降低 30-50% LLM 成本(vs 朴素全量 system prompt)
- ✅ Identity / Soul 抽象让"Agent 个性化"成为产品功能而非 prompt 黑魔法

### Negative
- ⚠️ `agentcook-storage` 复杂度增加(从纯关系型 → 关系型 + 向量)
- ⚠️ 隐私合规要求 — 用户 PII 进入记忆库要明确告知 + 提供删除接口
- ⚠️ Token 成本 — Memory 召回过多会撑爆 context,需 compaction(Phase 2 Agent A 写)
- ⚠️ 测试复杂度 — 跨会话 / 跨设备 / 召回准确度 / prompt injection 防御都要覆盖

### Risk
- ❗ pgvector 在 PostgreSQL < 14 性能差 → 强制要求 PG 15+,影响部署文档
- ❗ Auto Dream 默认开启会增加后台成本 + 用户不可控感 → 决定默认关,作为"高级开关"
- ❗ Identity 创建时锁定后无法修改 → 用户首次创建必须有"reset Agent"功能(等于删除重建)

## Alternatives Considered

| 方案 | 否决理由 |
|---|---|
| 不做记忆体系,纯无状态 chat | 2026 年用户期待已成默认,无记忆 = 没有差异化 |
| 记忆全放 system prompt 不做向量召回 | 上下文很快超长,LLM 成本爆炸 |
| 用 LangChain Memory 现成实现 | 与 LangGraph 集成需自己写,且无层次结构 + 无用户控制 UI |
| 只做短期会话记忆,跨会话不记 | 用户体验断层,无法支撑"我的 Agent" 这种核心产品语言 |

## Implementation

### Phase 1 (Day 6-15)
- Agent A:在 `agentcook-core` 写 `IdentityProtocol` + `SoulProtocol` + `MemoryStoreProtocol`(只接口,不实现)
- 写 ADR-011 内"未决事项"评估笔记(向量库选型 / 召回算法 / Auto Dream 默认),Phase 2 拍板

### Phase 2 (Day 16-25)
- Agent A:Day 17 finalize 向量库选择;Day 19 实现 OpenAI embedding 接入;Day 21 实现 hybrid 召回;Day 22 写 compaction / pruning(本 ADR finalize 为 Accepted)
- Agent C:Day 18 docker-compose 加 pgvector 扩展

### Phase 3 (Day 26-37)
- Agent B:admin 写 "Memory 浏览器" UI(可查看 / 编辑 / 删除)
- Agent B:app 写 "Identity / Soul 配置向导"(首次启动)

### Phase 4 (Day 38-47)
- Agent A:Auto Dream 后台任务(可选 feature,默认关)

### Phase 5 (Day 48-57)
- Agent C:prompt injection 防御测试(攻击 Identity / Soul 修改路径)
- Agent C:跨会话 / 跨设备记忆同步 e2e 测试

## Educational Value(教程素材)

本 ADR 设计可独立成为教程一章:**《如何为 Agent 设计记忆与人格》**

讲解大纲(脱敏版):
1. 为什么 2026 年 Agent 必须有记忆 — 用户期待已成默认
2. 四层栈:Identity / Soul / Memory / Diary 的边界与职责
3. System prompt 注入顺序与 prefix-cache 经济学
4. pgvector vs 独立向量库的成本权衡
5. 用户控制权:为什么必须给"Memory Flush"按钮
6. 一个真实生产系统(脱敏)是怎么把 Identity 设计成不可变的

## References

- pgvector: https://github.com/pgvector/pgvector
- Anthropic prompt caching docs(prefix-cache 经济学)
- 该真实工程 PE(phoenix-engine)的 IDENTITY / SOUL / MEMORY / diary / Auto Dream / Memory Flush 体系 — 经过生产验证的层次结构哲学
