# ADR-017: chat 端点接真 LLM(Phase 4.6,提前从 roadmap Day 50)

## Status

**Accepted** (2026-06-01,Phase 4.6 验证完成时刻)

## Context

Phase 3 Day 9 上线的 `agentcook/src/agentcook_app/routers/chat.py` 第 33-100 行的 `_stream_mock_response` 是 **mock 实现**:返回预录英文字符串("I'd be happy to help you with that!..."),不真调 LLM。

原计划在 Phase 5 模糊承诺(`chat.py` 第 7-12 行注释 "Phase 5 replaces the mock LLM with real provider calls"),**roadmap 未明确具体 Day**(roadmap Day 50 是 locust 性能测试,不是 chat 接真 LLM)。但 2026-06-01 P1 MVP 验证暴露**真 chat 必要性**:

- agentcook-app 前端 chat 界面已经跑通(http://localhost:5174/chat)
- 作者倾向"先用免费域名 + 暂不真上线 + 等教程完成再换真域名"路线
- **如果 chat 还是 mock,demo 对外演示价值大打折扣**(任何访客测一下就知道是假的)
- ADR-016 已经把默认 Provider 切到 Qwen qwen-turbo(免费额度内),`OpenAIProvider.stream_chat()` 接口完整 ready,**改造成本极低**(~2 h)

按"立刻干"原则,**Phase 4.6 提前 chat.py 注释承诺的 Phase 5 "chat 接真 LLM"任务**,作为 P1 验证后第一件事。(原 2026-06-01 草稿本段误写 "roadmap Day 50",已修正)

## Decision

### 1. 改造范围

仅改 `agentcook/src/agentcook_app/routers/chat.py`,**保留 mock 作为 env var fallback**:

| 元素 | Phase 3 现状 | Phase 4.6 改造后 |
|---|---|---|
| `_stream_mock_response` | 返回预录英文 SSE | **保留**,作为 `AGENTCOOK_CHAT_MOCK=true` 时的 fallback |
| `_stream_real_response`(新增) | (不存在) | 调 `provider.stream_chat()` 包装 `ChatChunk → ChatStreamFrame` |
| `_get_provider()`(新增) | (不存在) | lazy singleton,首次请求时 `create_provider()` 初始化 |
| `_use_mock()`(新增) | (不存在) | env var 切换逻辑(详 §2) |
| `chat_stream` 路由 | 固定调 mock | 根据 `_use_mock()` 选 generator |

### 2. Mock vs Real 切换逻辑(env var 优先级)

```python
def _use_mock() -> bool:
    # 显式强制 mock
    if os.environ.get("AGENTCOOK_CHAT_MOCK", "").lower() in ("true", "1", "yes"):
        return True
    # 没配 provider env → fallback mock(CI / contract test 场景)
    if not os.environ.get("AGENTCOOK_LLM_PROVIDER"):
        return True
    return False
```

| 场景 | env 设置 | 行为 |
|---|---|---|
| 生产 / staging(Phase 4.5 真上线) | `AGENTCOOK_LLM_PROVIDER=qwen` + `QWEN_API_KEY=sk-...` | **真 qwen** |
| 本地 dev(`make dev`) | 同上(.env 注入) | **真 qwen** |
| CI / 单元测试 | 不设 `AGENTCOOK_LLM_PROVIDER` | mock(自动 fallback) |
| 临时切回 mock 调试 | `AGENTCOOK_CHAT_MOCK=true` | mock(显式强制) |

### 3. SSE 协议兼容性

**前端 `useSseChat.ts` 0 改动**。`ChatStreamFrame` 字段保持完全一致:

| 帧位置 | 字段 |
|---|---|
| 首帧 | `role="assistant"` + `content=""` + `done=false` + `session_id` |
| 内容帧 | `role="assistant"` + `content="<delta>"` + `done=false` |
| 终止帧 | `role="assistant"` + `content=""` + `done=true` + `metadata` |

**Metadata 字段在终止帧扩展**(向后兼容):

```json
{
  "model": "qwen-turbo",
  "provider": "OpenAIProvider",
  "request_id": "abc123",
  "duration_ms": 1234.5,
  "output_chars": 87,
  "finish_reason": "stop",
  "source": "provider"
}
```

(mock 的 metadata 加 `"source": "mock"` 区分)

### 4. 错误处理(SSE-friendly)

Qwen API 失败(rate limit / 5xx / network)时,**不抛 500**,而是发**带 error 的终止帧**:

```json
data: {"role":"assistant","content":"","done":true,"error":"RateLimitError: ...","metadata":{...}}
```

前端 `useSseChat` 收到 `done: true` + `error` 字段时可以提示用户重试。

### 5. Phase 4.6 不做的事(留 Phase 5)

| 功能 | 留到 |
|---|---|
| Memory 加载(根据 session_id 拉历史会话) | Phase 5 Day 51 |
| Tool calling(plugin_ids 字段真激活)| Phase 5 Day 52 |
| Sandbox runner(plugin 沙箱执行) | Phase 5 Day 53 |
| Hook runtime pre/post hooks | Phase 5 Day 54 |
| Anthropic / Zhipu provider fallback 链 | Phase 5 Day 55 |
| Cloudflare Turnstile + Rate Limit 防刷(详 ADR-016 §5) | Phase 5 Day 56 |

## Consequences

### 正面

- **demo 真有 AI** — 任何访客真测 chat,得到 qwen-turbo 真回答,不再被发现"假装能聊"
- **零额外成本** — Qwen 免费额度足够 P1/P2 阶段流量,继承 ADR-016 决策
- **SSE 协议向后兼容** — 前端 `useSseChat.ts` 0 改动,4 Agent 协作不打断
- **mock fallback 保留** — CI / 单测 / 离线 dev 不受影响
- **观测性继承** — `OpenAIProvider.stream_chat()` 已经 wired 进 OTel span(`model.openai.stream_chat`),Jaeger / Langfuse 自动 trace
- **roadmap 提前 1.5 周** — Phase 5 Day 50 任务提前到 Phase 4.6,Phase 5 实际启动时 chat 已经 ready

### 负面

- **Phase 5 Memory / Tool calling / Sandbox 接入时需要再改 chat.py** — 但这是预期的渐进增量,不是返工
- **Qwen 免费额度被刷风险** — 详 ADR-016 §5 Phase 5 backlog #11 接 Cloudflare Turnstile

### 中性

- Mock 保留增加 ~80 行代码,但**保留比删除更安全**(Phase 5 测试可能回需要 mock)

## Validation(2026-06-01 实测)

测试场景:作者在 http://localhost:5174/chat 发"你是谁"。

| 检查 | 结果 |
|---|---|
| chat.py reload | ✅ uvicorn `--reload` 自动检测,无 import error |
| `_use_mock()` 返回 false | ✅ `.env` 设了 `AGENTCOOK_LLM_PROVIDER=qwen` |
| `_get_provider()` 初始化 | ✅ lazy singleton,DashScope OpenAI-compatible endpoint |
| `stream_chat()` 真调 qwen-turbo | ✅ 看终端 1 OTel span `model.openai.stream_chat / model.name=qwen-turbo` |
| SSE 帧前端正常渲染 | ✅ agentcook-app 真显示中文 markdown 流式 |
| 回答内容真 qwen | ✅ 输出 "我是通义千问,阿里巴巴集团旗下的通义实验室..." mock 不可能返回 |
| Token 消耗 | ✅ 单次约 30-100 token,免费额度内 |

## Source

- 改动文件: `agentcook/src/agentcook_app/routers/chat.py`(144 行 → 259 行,+115 行)
- 决策依据: ADR-016(LLM 默认 Provider Qwen)+ P1 验证后作者路线确认("先用免费域名,chat 现在就接真 qwen")
- 关联文档: `_internal/operations/cloudflare-pages-mvp-cookbook.md` §2 P1.4 + §3 坑 5(原 mock 限制)

## Related

- ADR-016 LLM 默认 Provider Qwen(本 ADR 是 ADR-016 的"消费端"具体落地)
- Phase 5 backlog Day 51-56(Memory / Tool / Sandbox / Hook 逐项接入)
- `agentcook-providers/src/agentcook_providers/openai_provider.py` `stream_chat()` 第 228-340 行(底层流式接口)
