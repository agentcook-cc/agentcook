# ADR-018: 账号配额机制 + 分层模型(qwen-turbo → glm-4-flash 降级)

## Status

**Accepted** (2026-06-03,Phase 5 Day 54 协调员代办起草,作者拍 v1 = 2 次/账号)

## Context

Phase 4.6 chat 端点接真 Qwen 后(ADR-017),demo 真上线对陌生访客开放,需要**商业演示防滥用**机制:

- 阿里百炼 qwen-turbo 免费额度有限(~50 万 token/月),被刷单次攻击 30+ 万 token 可瞬间击穿
- 未登录访客 0 成本调 chat,**没有自然刹车**
- 但完全 429 拒绝 = 失去演示价值
- Day 50 C 实测 500u mock 系统极限 + 100u 真 qwen baseline 38K token(76% 单次预算)

作者 2026-06-02 拍 task #12 提出:**每账号 2 次免费 qwen-turbo,超出降级 glm-4-flash**(智谱完全免费 + 真智能,Phase 5 Day 52-54 A 已实现 zhipu provider)。

## Decision

### 1. 配额机制 v1(2026-06-03 作者拍板 A)

| 维度 | v1 |
|---|---|
| **默认免费次数** | **2 次/账号**(选项 A) |
| **配额单位** | 账号(JWT sub 字段标识) |
| **配额重置** | **不重置 v1**(永久 2 次,后续 v2 加日重置/月重置) |
| **超额行为** | **自动降级到 glm-4-flash**(不返回 429,体验不中断) |
| **未登录访客** | 共享 IP 配额(Cloudflare Turnstile + Rate Limit / Phase 5 backlog #11) |

### 2. 分层模型链

```
登录用户调 chat:
  ① free_questions_used < 2 → qwen-turbo(主)
  ② free_questions_used >= 2 → glm-4-flash(降级,完全免费 + 真智能)
  ③ glm-4-flash 不可用 → qwen-plus(付费,作者承担,有 monthly 上限)
  ④ qwen-plus 也不可用 → echo provider(返回 mock,保 demo 不 500)

未登录访客调 chat:
  - Cloudflare Turnstile 验证(防机器人)
  - Cloudflare Rate Limit:10 req/IP/天
  - 走 glm-4-flash 默认(免费无配额)
```

### 3. 数据库 schema

```sql
-- agentcook-java/agentcook-infrastructure Flyway migration V4__add_quota.sql
ALTER TABLE users ADD COLUMN free_questions_used INTEGER DEFAULT 0 NOT NULL;
ALTER TABLE users ADD COLUMN free_questions_quota INTEGER DEFAULT 2 NOT NULL;
ALTER TABLE users ADD COLUMN quota_reset_at TIMESTAMP NULL;  -- v2 预留(日/月重置)
```

### 4. 代码改动范围

| 文件 | 改动 | Owner |
|---|---|---|
| `agentcook-java/agentcook-infrastructure/.../V4__add_quota.sql` | 新增 migration | D |
| `agentcook-java/.../domain/UserAggregate.java` | 加 freeQuestionsUsed + freeQuestionsQuota 字段 + consumeFreeQuestion() 业务方法 | D |
| `agentcook-java/.../api/QuotaController.java` | GET `/api/v1/quota` 返回当前配额 | D |
| `agentcook/src/agentcook_app/middleware/quota.py` | 新增 middleware:JWT sub → 查 Java quota → 选 provider | A |
| `agentcook/src/agentcook_app/routers/chat.py` | `_stream_real_response` 加 `provider_override` 参数 | A |
| `agentcook-providers/.../factory.py` | 已支持 zhipu(A Day 52-54 落地,本 ADR 配合) | A ✅ |
| `agentcook-app/src/components/ChatInput.tsx` | 显示"剩余免费 X 次"+ 降级提示 | B |

### 5. 配置化(env var)

```bash
AGENTCOOK_FREE_QUOTA_DEFAULT=2          # v1 默认 2 次(作者拍 A)
AGENTCOOK_QUOTA_FALLBACK_PROVIDER=zhipu # 超额降级到哪个 provider
AGENTCOOK_QUOTA_FALLBACK_MODEL=glm-4-flash
AGENTCOOK_QUOTA_RESET_INTERVAL=never    # v1 不重置;v2 加 daily/monthly
```

### 6. Phase 5 / 后续路线

| Phase | 任务 |
|---|---|
| **Phase 5 Day 55-56**(实施) | D Flyway V4 + Java UserAggregate / QuotaController / A Python middleware + chat.py 改造 / B 前端显示 |
| **Phase 5 Day 57** | 4 Agent 联调 + 集成测试(配额耗尽 → 降级 → 仍 glm-4-flash) |
| **Phase 5 buffer** | Cloudflare Turnstile + Rate Limit(Phase 5 backlog #11 / ADR-016 §5) |
| **教程发布后 v2** | 日/月重置 / 付费升级 / Stripe(超出 v1 范围) |

## Consequences

### 正面

- **demo 真上线零 LLM 烧爆风险**(配额 2 次 + 降级 glm-4-flash 完全免费 + Turnstile 防刷三层)
- **不中断体验**(超额不 429,降级 glm-4-flash 真智能,中文质量接近 qwen-turbo)
- **A Day 52-54 Zhipu provider 实现** = ADR-018 的直接 enabler
- **配置化默认 2** — v1 即可调,不改代码

### 负面

- **Java 端 V4 migration** = D Phase 5 Day 55-56 新增 ~半天
- **Python middleware quota.py** = A 新增 ~半天
- **前端 ChatInput 显示** = B ~2 h
- **跨语言 quota 同步增加 1 跳延迟** — Day 50 C perf baseline 不含,Phase 5 末 staging 重跑需含
- **未登录访客 glm-4-flash 默认** = 商业感知"什么都没付就用上了",demo 阶段不是问题

### 中性

- v1 = 2 次基于"商业演示极限"判断,真用户反馈后调到 5 次或更高
- 不重置 v1 = 简单实现,v2 加 daily/monthly 不破坏 backward compat

## Validation(实施后 Phase 5 Day 57)

- 单测:`test_quota_middleware.py` 5 场景(未登录 / 登录配额内 / 登录配额满 / glm-4-flash 不可用 fallback / config override)
- 集成测试:admin@agentcook.cc 登录 → chat 3 次 → 第 3 次应返回 `metadata.provider="zhipu" / model="glm-4-flash"`
- 前端 e2e:ChatInput "剩余 2 次" / 用完后 "已降级到 glm-4-flash"

## Source

- task #12("[Phase 5 backlog #13] 账号配额机制 + Zhipu provider + 分层模型")
- ADR-016 §5("demo 防刷 — Phase 5 backlog #11")
- ADR-017(chat 真接 qwen)
- 作者 2026-06-02 洞察 + 2026-06-03 拍板 v1 = 2 次/账号(A)
- Day 50 C `phase5-day50-performance-report.md` §6 旁路 + 100u 38K token 实测
- Day 52-54 A Zhipu provider 实现(commit 待 push)

## Related

- ADR-016 LLM 默认 Provider Qwen
- ADR-017 chat 端点接真 LLM
- Phase 5 backlog #11 Cloudflare Turnstile + Rate Limit
