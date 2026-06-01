# ADR-016: 默认 LLM Provider 切换到 Qwen (qwen-turbo)

## Status

**Accepted** (2026-06-01,Phase 4.5 真上线前确认)

## Context

Phase 4.5 demo.laoa.dev(原 demo.agentcook.cc)真上线前,作者提出**LLM 成本控制问题**:

- demo 站对陌生访客开放后,每次 chat 调用都消耗 LLM API quota
- 默认配置(OpenAI gpt-4o-mini,$0.15/M input + $0.60/M output)在被刷场景下 **单次攻击成本 ¥100+**
- agentcook 定位是"开源 + 教程配套 + 开发者优先",**信用卡烧 OpenAI 与定位错位**
- 作者持有阿里通义千问 API key,**DashScope 平台免费额度可覆盖 demo 流量**

**架构现状(实测 grep)**:
- `agentcook-providers/src/agentcook_providers/factory.py` 第 65-77 行已完整支持 Qwen,通过 DashScope OpenAI-compatible endpoint(`https://dashscope.aliyuncs.com/compatible-mode/v1`)复用 `OpenAIProvider`
- `_DEFAULT_MODELS["qwen"]` 原值 `qwen-plus`,改造范围仅一行
- 教程 `roadmap.md` / `v6-architecture-rationale.md` / ADR-011 已把通义列为支持的 4 provider 之一
- Anthropic / Zhipu provider 当前为 NotImplementedError(Day 9-10 才落地),**Phase 4.5 实际可用 = openai + qwen + echo**

## Decision

### 1. 默认 Qwen 模型:`qwen-turbo`(从 `qwen-plus` 切换)

| 维度 | qwen-turbo(选定) | qwen-plus(原默认) | qwen-max |
|---|---|---|---|
| 速度 | ⚡ 快(~80 token/s) | 中 | 慢 |
| 质量 | 接近 gpt-4o-mini | 接近 gpt-4o | 接近 gpt-4o-128K |
| 免费额度 | **最慷慨** ⭐ | 较少 | 小 |
| 适合 | **demo 默认 / 大流量** ⭐ | 平衡 / 中流量 | 长文档 / reasoning |

**理由**:demo.laoa.dev 真上线后,流量优先选**免费额度最大 + 速度最快**的 turbo;质量虽略低于 plus,但**作为教程配套 demo 完全够用**(教程目标是讲架构,不是炫模型)。

### 2. 默认 Provider 切换路径

**不改 factory.py 的默认值,通过环境变量切换**:

```bash
# 生产环境(K8s ConfigMap / Helm values)
AGENTCOOK_LLM_PROVIDER=qwen

# 本地开发(.env)
AGENTCOOK_LLM_PROVIDER=qwen
QWEN_API_KEY=sk-xxx
```

**理由**:保留 factory.py 的 "no default provider" 设计,**强制用户显式选择**,避免无意识烧错 provider 的钱。

### 3. Fallback 链(`agentcook-providers/fallback.py` 内 v6 配置)

```
demo.laoa.dev 默认链:
  primary:  qwen-turbo      (免费额度内)
  fallback: qwen-plus       (turbo 免费额度满,降级到付费 plus 仍是阿里生态)
  emergency: echo           (qwen 全挂时返回 mock,保 demo 不 500)

未来 staging:
  + anthropic claude (Day 9-10 provider 落地后接入)
  + openai gpt-4o-mini (信用卡 fallback,$5 月度上限)
```

### 4. Phase 4.5 真上线时的 K8s Secret 注入

```yaml
# agentcook-cc/deploy/helm/agentcook/values-staging.yaml + values-prod.yaml
env:
  AGENTCOOK_LLM_PROVIDER: qwen
  QWEN_MODEL: qwen-turbo

envFrom:
  - secretRef:
      name: agentcook-llm-keys

# 作者执行(Phase 4.5 真上线前)
kubectl create secret generic agentcook-llm-keys \
  --from-literal=QWEN_API_KEY=sk-xxx \
  -n agentcook-prod
```

### 5. demo 防刷(Phase 5 backlog 第 11 项)

千问免费额度满了会返回 429,但被恶意刷会快速耗尽免费额度。Phase 5 接入:

- **Cloudflare Turnstile**(免费验证码,登录 + chat 前验证)
- **Cloudflare Rate Limit**(免费 10 req/IP/天)
- **Traefik per-user rate limit**(注册用户 100 次/天)

## Consequences

### 正面

- **demo 真上线零 LLM 成本**(在 Qwen 免费额度内)
- **国内访问速度更快**(DashScope 国内机房 vs OpenAI 海外)
- **与 agentcook 开源 + 教程配套定位对齐**(不烧美元)
- **factory.py 改动仅一行**(`qwen-plus` → `qwen-turbo`),零回归风险
- **教程不需大改**(roadmap / ADR-011 早已支持 4 provider 架构)

### 负面

- qwen-turbo 质量略低于 gpt-4o-mini(差距约 5-10%,demo 场景无感)
- 千问免费额度有上限(阿里百炼按月配额,具体值以阿里实时公告为准),被刷场景需 Phase 5 防刷接入
- 教程示例代码中"如何接 OpenAI"段需补"如何接 Qwen"对照

### 中性

- 不影响付费用户(自带 API key 走自己的 provider)
- 不影响 OpenAI/Anthropic 测试(test_providers.py 的 mock 不受影响)

## Source

- `agentcook-providers/src/agentcook_providers/factory.py` (第 65-77 行,Qwen provider 实现)
- `agentcook-providers/src/agentcook_providers/__init__.py` (fallback 链注释)
- `_internal/L3-strategy/roadmap.md` §2(4 provider 架构)
- `_internal/L3-strategy/v6-architecture-rationale.md` §24(provider 适配)
- ADR-011 §Embedding (通义/智谱备选历史决策)

## Related

- ADR-006 Blue-Green deployment(domain 切换)
- ADR-011 Agent memory(embedding provider 同款多 provider 思路)
- Phase 5 backlog #11:Cloudflare Turnstile + Rate Limit 防刷接入
