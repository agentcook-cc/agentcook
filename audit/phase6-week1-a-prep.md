# Phase 6 Week 1 — A 视角准备（Day 66 下午起草，Day 68 真启动）

> 协调员 Day 66-69 brief §3 A 段：Day 66 下午 prep outline + Anthropic 真栈手动测试 SOP；Day 68 下午 #20 真启动 commit。
> 本文件 = 上面两段的设计稿 + Anthropic SOP，作为 Day 68 #20 真实施的施工图。

---

## §1 #20 Python Turnstile middleware — spike outline

### 1.1 任务定位

Phase 5 backlog #11（Cloudflare Turnstile + Rate Limit）在 Day 62 cascade 完成 D Java（cascade 第 1 环）+ C Cloudflare Worker（cascade 第 0 环，边缘层）+ B 前端 widget（cascade 第 3 环）。**Python chat endpoint 这一环（cascade 第 2 环）当前未接入** — 这是 Phase 5 backlog #20 / 本 spike 的目标。

接入路径：

```
B 前端 widget → 拿 Turnstile token → header 带给 Python /api/v1/chat/stream
        ↓
Python chat 路由 → A 新 middleware/turnstile.py 验证 → 通过才进 _stream_real_response
        ↓
(可选优化) middleware 调 C Cloudflare Worker 边缘验证(50ms vs 200ms)
        ↓ or
(fallback) middleware 直调 Cloudflare siteverify 官方 endpoint
```

### 1.2 上游 cascade 第 0 环（C）+ 第 1 环（D）实测 contract

**C Cloudflare Worker `workers/turnstile-verify/src/index.ts`**：

```
POST /verify
Request body : {token: string, remoteIp?: string}
Response 200 : {success: true, ...metadata}
Response 401 : {success: false, error_codes: string[]}
```

部署位置：`turnstile.agentcook-cc.workers.dev`（Day 68 wrangler 真 deploy 后生效；当前未上线）。

**D Java `cc.agentcook.api.auth.TurnstileVerifier`**（Day 62 c3eeb10）：

- `@Component` Spring Bean，构造注入 `agentcook.turnstile.secret`
- Dev mode：secret 为空 → short-circuit 返 `true`（Phase 3 dev login / Phase 5 tests 不需要真账号）
- Prod mode：设 `AGENTCOOK_TURNSTILE_SECRET` env → 真调 Cloudflare siteverify
- Fail-closed：upstream 非 200 / 超时 / 解析错都返 `false`

**Python middleware 与 Java 设计原则保持一致**（dev short-circuit + prod fail-closed）。

### 1.3 接口设计（参照 middleware/quota.py 模式）

#### 1.3.1 模块结构

```
agentcook/src/agentcook_app/middleware/
├── __init__.py          # 已有；本 spike 加 export Turnstile* + Verifier
├── quota.py             # 已有（ADR-018 Day 56）
└── turnstile.py         # 新增（本 spike）
```

#### 1.3.2 dataclass + class skeleton

```python
@dataclass(frozen=True, slots=True)
class TurnstileDecision:
    verified: bool          # 终极判定
    reason: str             # "verified" | "dev_short_circuit" | "missing_token" | "worker_unavailable" | "cloudflare_rejected"
    error_codes: tuple[str, ...] = ()  # Cloudflare error_codes pass-through

class TurnstileVerifier:
    def __init__(
        self,
        *,
        worker_url: str | None = None,    # 默认 https://turnstile.agentcook-cc.workers.dev/verify
        cloudflare_secret: str | None = None,  # fallback：直调 siteverify
        http_client: httpx.AsyncClient | None = None,
        dev_short_circuit: bool = False,  # 测试 + dev mode
        timeout_seconds: float = 3.0,
    ) -> None: ...

    async def verify(
        self,
        token: str | None,
        *,
        remote_ip: str | None = None,
    ) -> TurnstileDecision: ...
```

#### 1.3.3 决策流程

```
1. dev_short_circuit=True 或 cloudflare_secret 为空且 worker_url 为空
   → 返 TurnstileDecision(verified=True, reason="dev_short_circuit")
2. token 为空 / 空字符串
   → 返 TurnstileDecision(verified=False, reason="missing_token")
3. worker_url 设了 → POST {token, remoteIp} 到 Worker
   - 200 + success=true → verified
   - 200 + success=false → cloudflare_rejected + error_codes pass-through
   - 5xx / 超时 / 解析错 → worker_unavailable + fail-closed verified=False
4. worker_url 为空但 cloudflare_secret 设了 → 直接 siteverify
   - 同上 3 步语义
```

**fail-closed 原则**：upstream 任何故障默认 `verified=False`，让前端用户重试。**不 short-circuit 通过** —— Day 62 D Java 同款选择（详 TurnstileVerifier docstring）。

#### 1.3.4 chat.py 接入点

```python
# routers/chat.py
async def chat_stream(
    request: ChatStreamRequest,
    turnstile_token: Annotated[str | None, Header(alias="X-Turnstile-Token")] = None,
    client_ip: Annotated[str | None, Header(alias="X-Forwarded-For")] = None,
) -> StreamingResponse:
    ...
    if not _use_mock():
        decision = await get_turnstile_verifier().verify(turnstile_token, remote_ip=client_ip)
        if not decision.verified:
            raise HTTPException(
                status_code=401,
                detail={
                    "reason": decision.reason,
                    "error_codes": list(decision.error_codes),
                },
            )
    ...
```

**dependency 注入**：`get_turnstile_verifier()` lazy singleton（同 `_get_provider()` 模式），env vars 配置：

- `AGENTCOOK_TURNSTILE_WORKER_URL`（推荐：Day 68 wrangler 真 deploy 后填写）
- `AGENTCOOK_TURNSTILE_SECRET`（fallback：直调 siteverify）
- `AGENTCOOK_TURNSTILE_DEV_SHORT_CIRCUIT=true`（dev / 测试默认开）

### 1.4 测试设计（≥ 5 场景）

参照 `tests/test_quota_middleware.py` 的 `_MockTransport(httpx.AsyncBaseTransport)` 模式：

| #           | 场景                                                       | 期望                                                                    |
| ----------- | ---------------------------------------------------------- | ----------------------------------------------------------------------- |
| 1           | dev_short_circuit=True                                     | verified=True, reason="dev_short_circuit"（不调 Worker）                |
| 2           | token 为 None                                              | verified=False, reason="missing_token"（不调 Worker）                   |
| 3           | Worker 返 200 success=true                                 | verified=True, reason="verified"                                        |
| 4           | Worker 返 200 success=false + error_codes                  | verified=False, reason="cloudflare_rejected" + error_codes pass-through |
| 5           | Worker 返 500 / 超时 / 连接拒绝 / 非 JSON                  | verified=False, reason="worker_unavailable"（fail-closed）              |
| 6（option） | worker_url 为空但 cloudflare_secret 设了 → 直调 siteverify | 同 3-5 但 URL 是 cloudflare 官方                                        |
| 7（option） | dependency injection lazy singleton 验证                   | `get_turnstile_verifier()` 同对象 2 次调用                              |

预估 PASS 数 **8-10**（与 Day 56 quota 16 PASS 同款，覆盖主路径 + 异常路径）。

### 1.5 cascade D → A → C 三方对齐

| 角色         | 已有                                                                     | 待 #20 接入                                                                       |
| ------------ | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **D Java**   | `TurnstileVerifier` Bean / `agentcook.turnstile.secret` / Day 62 c3eeb10 | ✅ 0 改动（Python 独立链路）                                                      |
| **A Python** | quota.py 模式 / Day 56 bd74f56                                           | 🟡 新增 turnstile.py + chat.py 接入 + 5-7 tests（本 spike）                       |
| **C Worker** | turnstile-verify worker code / Day 62 0bd6ee1                            | ⏳ Day 68 wrangler 真 deploy（作者执行）                                          |
| **B 前端**   | widget 接入 admin/app login / Day 62 6762ce2                             | 🟡 chat 路径 header 转发（Phase 6 第 1 周 B #23 之外的小改 — 待 A spike 后 ping） |

**A 不阻塞 C** — C Worker 即使未真 deploy，A 用 `worker_url=None + cloudflare_secret=<dev>` 双链路兜底 + 测试用 `_MockTransport` 完全独立验证。Day 68 wrangler 真 deploy 后 A 改 env var 即可切真栈。

---

## §2 Anthropic 真栈手动测试 — SOP（作者执行）

### 2.1 为什么 A 不直接跑

按 memory `feedback-agent-physical-limits-no-gui` + cookbook 23 子项 #23（wrangler 真 deploy = 作者执行原则）：**Agent 不真调付费 / 公开外部 API**。理由 2 条：

1. **付费成本**：1 次 chat API call 直接产生外部消费，不该由 Agent 决定
2. **API key 安全**：Anthropic API key 是用户机密，Agent 不应进入 commit / progress / audit 任何 trace

A 同款节奏 Day 62 早晨 commit + push（明确授权）+ Day 68 wrangler 真 deploy（作者执行）。

### 2.2 作者执行步骤（< 5 min）

```bash
# 1. 申请 / 复用真 API key
#    https://console.anthropic.com/settings/keys  → Create Key
#    复制 sk-ant-... 格式 key

# 2. 设 env（推荐 .env 文件持久化，或临时 shell export）
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. 装 SDK（Buffer Day 59 用 mock 兜底，真栈第一次需要装）
cd ~/workspace/accio-work/agentcook-cc
uv pip install "anthropic>=0.40"

# 4. 1 次真 API call verify（≤ 100 token 测试问，成本 < $0.01）
python -c "
import asyncio
from agentcook_providers import AnthropicProvider
from agentcook_core import Message

async def main():
    provider = AnthropicProvider.from_env()
    response = await provider.chat([
        Message(role='user', content='Reply with exactly: PHASE_6_READY')
    ], max_tokens=20)
    print(f'model: {response.message.content!r}')
    print(f'tokens: in={response.usage.input}, out={response.usage.output}')
    print(f'finish: {response.finish_reason}')

asyncio.run(main())
"

# 5. 预期输出
#    model: 'PHASE_6_READY'
#    tokens: in=15, out=5  (差几个 token 正常)
#    finish: stop
```

### 2.3 失败排查

| 现象                            | 排查                                                                                  |
| ------------------------------- | ------------------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY is required` | 步骤 2 没 export，或换了 shell 没 source `.env`                                       |
| `Invalid API key`               | key 复制少字符 / 在 console 已 revoke / billing 没启                                  |
| `Connection error` / timeout    | 网络阻塞 anthropic.com（国内某些环境可能需 VPN）                                      |
| 401 `permission_error`          | key 没启 `messages` scope / org 配额耗尽                                              |
| `model_not_found`               | env `ANTHROPIC_MODEL` 设了 deprecated model — 改 `claude-sonnet-4-6` 或不设走 default |

### 2.4 测试通过 ack

作者 verify 完后 ping A，A Day 67 audit 写 "Anthropic 真栈 manual verify ✅ by author"，不进 commit、不进 git history、不留 key trace。

---

## §3 Day 67-68 A 时序预告

| Day                         | 时段                | 任务                                                                                                                                                                                                                                     |
| --------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Day 67 上午** 09:00-12:00 | A 段 final audit    | Python 638 PASS 重跑（实测）→ Anthropic 真栈 verify SOP（作者执行，A 收 ping）→ A 段写入 `audit/day-67-pre-launch-final-audit.md` → commit 双仓                                                                                          |
| **Day 67 跨 repo verify**   | brief §6 #22 制度化 | `cd agentcook-cc && git status` clean + `cd agentcook && git status` clean(允许 untracked)                                                                                                                                               |
| **Day 68 下午** 13:00-17:00 | #20 真启动          | 新建 `agentcook/src/agentcook_app/middleware/turnstile.py` ~180 行 + 改 chat.py 加 `X-Turnstile-Token` header / `X-Forwarded-For` + 新建 `agentcook/tests/test_turnstile_middleware.py` ~250 行 / 8-10 PASS + commit + push agentcook-cc |
| **Day 68 verify**           | A 自检 + 协调员     | `pytest agentcook/tests/test_turnstile_middleware.py -v` 8-10/N PASS + 全量回归 638 + 8-10 PASS / 0 fail                                                                                                                                 |
| **Day 69**                  | A standby           | D0 等 Day 70 首发                                                                                                                                                                                                                        |

---

## §4 Reverse fact-check（Day 66 起草时）

### #1 Anthropic 真栈 = A SOP + 作者执行（不直跑）

按 memory `feedback-agent-physical-limits-no-gui` + cookbook 23 子项 #23（wrangler 真 deploy 同款）。A 不真调付费 API，写 SOP 留作者执行；测试代码全用 mock client（详 Day 59 commit 002e8a8 的 `_stub_anthropic_module` + `_build_mock_provider` 双层兜底模式）。

### #2 chat.py turnstile 接入 = 仅在 real provider 路径

Mock 路径（`AGENTCOOK_CHAT_MOCK=true`）继续不做 turnstile 验证 — 这是 contract test / 单元测试 / CI 默认走的路径，加 turnstile 会让所有现有 test 全挂。同款设计：quota middleware 也是仅 real 路径生效。

### #3 不阻塞 C Day 68 wrangler 真 deploy

A `turnstile.py` 设计支持 3 种 mode（dev_short_circuit / direct cloudflare_secret / worker_url）。Worker 没上线时用前两种，Worker 上线后 env 切换 `AGENTCOOK_TURNSTILE_WORKER_URL` 即可。A spike 不卡在 C 真 deploy 进度上。

### #4 不动 Helm / spec / Cloudflare DNS / 任何 host 配置

A 范围严格限定 `agentcook/src/agentcook_app/middleware/turnstile.py` + `agentcook/src/agentcook_app/routers/chat.py` 改一处 + `agentcook/tests/test_turnstile_middleware.py` 新增。其他全 0 改。

---

## §5 给协调员的事实陈述

- Day 66 下午 prep 完成（本文件 ~225 行）
- C Day 62 Worker contract + D Day 62 Java contract 已 grep verify（实测引用代码段落，不脑补）
- A #20 spike 设计完整：架构 / 接口 / cascade / 测试 / env 配置 / 失败兜底全段
- Anthropic 真栈 = A SOP + 作者执行（reverse fact-check #1）
- 双仓 git status 实测：`agentcook-cc` clean / `agentcook` 1 untracked 是 C `phase6-wrangler-prep.md`（非 A 范围）
- Day 67-68 时序明确：Day 67 上午全量回归 + audit / Day 68 下午 #20 真实施
- 0 阻塞他人（C / D / B 各自 Day 66-67 工作不依赖 A）
