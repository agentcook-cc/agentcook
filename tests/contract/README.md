# Pact Contract Tests

Owner: Agent C. Implements ADR-007 测试金字塔 — Pact 契约层。

## 当前覆盖

| Consumer | Provider | Status | Pact spec |
|---|---|---|---|
| `agentcook-admin` | `echo-api`(sample) | ✅ Day 10 真链路通(3 PASSED in 2.59s)| V3 |

`echo-api` 是 `EchoProvider` 的 FastAPI sample wrapper (`sample_provider/main.py`),Day 22 Agent A 用真正的 `agentcook` FastAPI 主壳替换。

---

## 链路概览

```
┌──────────────────┐                                     ┌──────────────────┐
│ test_01_consumer │  declares interaction               │  test_03_provider│
│      _echo.py    │  ─── pacts/*.json ────┐             │ _verify_echo.py  │
└──────────────────┘                       │             └────────┬─────────┘
        │                                   ▼                      │ pact-verifier
        ▼                       ┌────────────────────┐             │  pull contract
   pact.v3 mock                 │ test_02_publish    │  PUT        │  + replay each
   (random port)                │ _to_broker.py      │ ─────►      │  request against
                                └────────────────────┘             │  live FastAPI
                                                                   │  (random port)
                                                                   ▼
                                ┌──────────────────────────────────────────┐
                                │  pact-broker @ localhost:9292            │
                                │  (docker-compose.dev.yml self-hosted)    │
                                └──────────────────────────────────────────┘
```

文件按数字前缀排序,确保 alphabetical run 顺序对(consumer → publish → provider verify)。**不要去掉前缀**,否则 verify 会跑在 publish 前,撞到 broker 上一次的 stale contract。

---

## 跑测试

```bash
cd ~/workspace/accio-work/agentcook-cc

# 前置:pact-broker 已在跑
docker compose -f docker-compose.dev.yml ps | grep pact-broker
# 期望:agentcook-pact-broker ... Up (healthy)

# 跑全链路
uv run pytest tests/contract/ -v
# 期望:3 passed in ~3s
```

**只跑 consumer**(开发本地不依赖 broker 时):

```bash
uv run pytest tests/contract/test_01_consumer_echo.py -v
```

**条件 skip**:`tests/contract/conftest.py` 的 `broker_url` fixture 在 broker 不可达时自动 skip,所以没起 broker 时整套 contract 测试静默跳过(不 fail CI)。

---

## 加一份新 Pact contract(SOP)

假设你要给 `agentcook-app` 加一个调 `chat-api` 的契约:

### 1. 写 consumer test

新建 `test_01_consumer_chat.py`(沿用 `01_` 前缀确保它在 publish 之前):

```python
from pact.v3 import Pact

CONSUMER = "agentcook-app"
PROVIDER = "chat-api"

@pytest.fixture(scope="module")
def chat_pact(pacts_dir):
    p = Pact(CONSUMER, PROVIDER).with_specification("V3")
    yield p
    p.write_file(str(pacts_dir), overwrite=True)

@pytest.mark.contract
def test_chat_streams_back_tokens(chat_pact):
    expected = {"chunks": ["hello", "world"]}
    (chat_pact.upon_receiving("a streaming chat request")
        .given("ChatService backed by Anthropic claude-sonnet-4-6")
        .with_request("POST", "/v1/chat/stream")
        .with_body(content_type="application/json", body={"text": "hi"})
        .will_respond_with(200)
        .with_body(content_type="application/json", body=expected))
    with chat_pact.serve() as mock:
        resp = httpx.post(f"{mock.url}/v1/chat/stream", json={"text": "hi"})
        assert resp.status_code == 200
```

### 2. publish 自动覆盖

`test_02_publish_to_broker.py` 用 glob 扫 `pacts/*.json`,新 contract 自动 publish,**不用动**。

### 3. 加 provider verify

不同 provider 各起一个 sample server。你可以选:

- 复用 `sample_provider`(在 `main.py` 里加 `/v1/chat/stream` route)
- 起新 sample(`sample_provider_chat/main.py`),写 `test_03_provider_verify_chat.py`

如果是同一 provider 名(`echo-api` / `chat-api` 不同),独立 verify 测试更干净。

### 4. 跑 + 验证

```bash
uv run pytest tests/contract/ -v
# 期望:N+3 passed(原 3 + 新加的 3)

# 看 broker
curl -s -u pact:pact http://localhost:9292/ | python3 -m json.tool | head
# 浏览器:http://localhost:9292(pact:pact)
```

---

## 排障

### 现象:consumer test `MismatchesError: Missing request`

实际 HTTP 请求没匹配上 mock interaction 声明。常见原因:

- URL 拼接错(`mock.url` 末尾**无** `/`,要写 `f"{mock.url}/v1/echo"`)
- query string 不匹配(用 `with_query_parameter` 单独声明,不是塞 path)
- body content-type 不一致(consumer 声明 `application/json` 但实际发 `text/plain`)

打印 `mock.url` 和实际请求 URL 对比即可。

### 现象:provider verify `connection refused`

provider FastAPI server 没起来。检查:

```bash
# 看 _free_port 给的端口
# 看 uvicorn 启动日志
uv run pytest tests/contract/test_03_provider_verify_echo.py -v -s
```

`-s` 让 pytest 不吞 stdout,uvicorn 的报错会出来。

### 现象:`docker-credential-desktop not found`(docker SDK 报错)

这是 host 残留,见 `_internal/audit/host-setup-guide.md §2.1`。

### 现象:`pb:latest-verification-results` link 返回空 list

**这是 link relation 含义,不是 publish bug**(Day 11 修正认识)。

`--publish-verification-results` 真发数据到 broker。verifier 输出会有这一行:

```
INFO: Verification results published to http://localhost:9292/pacts/provider/echo-api/consumer/agentcook-admin/pact-version/<hash>/verification-results/<N>
```

直接 GET 那个 URL 就能看到完整 `success/testResults/...`。`pb:latest-verification-results` link(用 GET /pacts/.../latest 拿到的)指的是 *list* endpoint,空列表常见(有些 broker 版本 / pact-version 链路只暴露单个 latest result,不是 list)。

要在 UI 里看 verify 状态,直接打开 `http://localhost:9292`(Basic Auth `pact:pact`),点 consumer/provider 的 row,verification 状态就在 row 上(✓ / ✗)。

---

---

## Day 22 — Agent A 接入清单(用 agentcook 主壳替换 sample_provider)

> ★ 本节 7 步 Day 12 由 C 当 mock A 跑通过一遍(只把 `agentcook` 替换成已存在的 `echo-api` 跑),每步给的 expected output **是实测捕获的**,不是想象的。

Day 22 你写完 `agentcook`(FastAPI 主壳)的真实 endpoint 后,按 7 步:

### 1. 写 consumer test

参考 `test_01_consumer_echo.py` 的形状,在同目录写一个新的 `test_01_consumer_chat.py`(数字前缀 `01_` 必保留,见上面 ordering 说明):

```python
# 关键改动 3 处:
CONSUMER = "agentcook-admin"   # 或 agentcook-app
PROVIDER = "agentcook"         # ★ 不是 echo-api 了

# 一个 test 函数内 register 所有 interaction(v3 限制,见 test_01 注释)
@pytest.mark.contract
def test_admin_agentcook_contract(pacts_dir):
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")
    (pact.upon_receiving("...")
        .given("...")
        .with_request("POST", "/v1/chat")
        .with_body(content_type="application/json", body={...})
        .will_respond_with(200)
        .with_body(content_type="application/json", body={...}))
    # ... 加更多 interaction(同一 test 内)

    with pact.serve() as mock:
        # 每个 interaction 用 httpx 跑一次
        ...

    pact.write_file(str(pacts_dir), overwrite=True)
```

### 2. 跑 consumer + publish

```bash
$ cd ~/workspace/accio-work/agentcook-cc
$ uv run pytest tests/contract/test_01_consumer_chat.py tests/contract/test_02_publish_to_broker.py -v --no-cov
```

实测期望(echo-api 当 mock 跑出来的真实输出):

```
tests/contract/test_01_consumer_echo.py::test_admin_echo_api_contract PASSED [ 50%]
tests/contract/test_02_publish_to_broker.py::test_publish_consumer_pacts PASSED [100%]
============================== 2 passed in 0.32s ===============================
```

`test_02_publish_to_broker.py` 用 `glob('pacts/*.json')` 自动扫,新 contract 自动 publish,**不要改**。

### 3. 启 agentcook 主壳

```bash
$ uv run python -m uvicorn agentcook_app.main:app --host 127.0.0.1 --port 8765 --log-level warning &
$ sleep 2
$ curl -s http://127.0.0.1:8765/health
```

实测期望:`{"ok":true}`(echo-api 实测如此;你的 agentcook 主壳要保证 `/health` 返同样 shape,或自己加 healthcheck endpoint 后改 verify fixture 里的 readiness 探测路径)。

### 4. 跑 verify_provider.py

```bash
$ uv run python tests/contract/scripts/verify_provider.py \
    --provider agentcook \
    --provider-base-url http://127.0.0.1:8765 \
    --provider-version "$(git rev-parse --short HEAD)"
```

实测期望(尾部输出):

```
          has status code 404
          has a matching body
          includes headers
            "Content-Type" which equals "application/json"

4 interactions, 0 failures
INFO: Verification results published to http://localhost:9292/pacts/provider/echo-api/consumer/agentcook-admin/pact-version/<hash>/verification-results/<N>
```

把 `4 interactions, 0 failures` / `verification-results/N` 当成 GO 信号。

### 5. 加正式 pytest provider verify

复制 `test_03_provider_verify_echo.py` → `test_04_provider_verify_agentcook.py`,改 3 处:

- `PROVIDER_NAME = "agentcook"`
- 子进程启动从 `tests.contract.sample_provider.main:app` 改 `agentcook_app.main:app`
- `provider_server` fixture 里 `cwd=repo_root` 不动(uvicorn 入口是 module path)

```bash
$ uv run pytest tests/contract/ -v --no-cov
```

实测期望(全链路):

```
tests/contract/test_01_consumer_echo.py::test_admin_echo_api_contract PASSED   [ 33%]
tests/contract/test_02_publish_to_broker.py::test_publish_consumer_pacts PASSED [ 66%]
tests/contract/test_03_provider_verify_echo.py::test_provider_satisfies_broker_contracts PASSED [100%]
============================== 3 passed in 2.68s ===============================
```

加上你的新 chat 测试后期望 4-5 passed。

### 6. 不要删 sample_provider

`tests/contract/sample_provider/` 是 EchoProvider 的 HTTP wrapper,后续教程章节(13-14 讲)引用作"最小可工作 provider 例子"。**留着,不再是主战场而已**。

### 7. Provider state setup(可选,Day 22 你大概率不需要)

如果某些 interaction 的 `given(...)` 状态不能仅靠"启 server"满足(eg. "user X is logged in"),provider 要起一个 state-setup endpoint:

```bash
$ uv run python tests/contract/scripts/verify_provider.py \
    --provider agentcook \
    --provider-base-url http://127.0.0.1:8765 \
    --provider-version "$(git rev-parse --short HEAD)" \
    # ...
# 然后手动加 verifier flag(目前 verify_provider.py 不支持,Day 22 你需要时让 C 加 --provider-states-setup-url 参数)
```

当前 echo-api / sample_provider 的 4 个 given(`EchoProvider is configured with prefix=Echo` / `EchoProvider rejects empty text` / `a profile exists with id 'alice'` / `no profile exists with id 'ghost'`)都是声明式描述,sample_provider hardcode 满足,无需 state setup。verifier 输出会有 `WARN: Skipping set up for provider state ... as there is no --provider-states-setup-url specified` — **良性**,不阻塞。Day 22+ 涉及 DB / auth state 时再处理。

### 6. 收尾 — 删 sample_provider?

**不要删 `tests/contract/sample_provider/`** — 它是 EchoProvider 的 HTTP wrapper,后续教程章节(13-14 讲)会引用它作为"最小可工作 provider 例子"。让它留着,只是不再是 contract 测试的主战场。

### 7. Provider state setup(可选,Day 22 你大概率不需要)

如果某些 interaction 需要 broker `given(...)` 状态(eg. "user X is logged in"),provider 要起一个 state-setup endpoint,verify 命令加 `--provider-states-setup-url=http://127.0.0.1:8765/_pact/provider_states`。当前 echo-api verify 输出里有 `WARN: Skipping set up for provider state` 是良性 — `given` 是声明式的,EchoProvider 不需要真 setup。Day 22+ 涉及 DB / auth state 时再处理。

---

## Day 24+ 自动化流程(pact-provider-ci.yml 切自动模式)

Day 22 写好 CI 脚手架,Day 24 起切自动模式 — **每次 A 改 spec 或 C 改 contract 测试,GitHub Actions 自动跑全链路**,失败 PR block。

### 触发路径(`.github/workflows/pact-provider-ci.yml` path-gated)

| 路径 | 谁会改 | 含义 |
|------|--------|------|
| `agentcook/**` | A | 主壳代码改 → 可能破坏既有契约 |
| `agentcook-core/**` | A | 业务逻辑改 → handler 行为变 → contract 不再满足 |
| `agentcook-providers/**` / `agentcook-storage/**` | A | 间接影响 handler 行为 |
| `tests/contract/**` | A 写 consumer / C 写 provider verify | 显式 contract 改动必须重跑 |
| `docs/api/v1.yaml` | A | Day 24 冻结后任何 spec 改动都应触发 contract drift 检查 |
| `pyproject.toml` / `uv.lock` | 全员 | pact-python 版本变,环境变 |
| `docker-compose.dev.yml` | C | broker / postgres 版本变 |
| `.github/workflows/pact-provider-ci.yml` | C | workflow 自身改 → 必跑自测 |

### 2 job 流程

```
push / PR  ─┐
            │
            ▼
   ┌────────────────────────┐
   │ consumer-publish (job1)│   1. service container 起 pact-broker(本地 :9292 同款)
   │ 起 broker → 跑 test_01_* + test_02_publish → 把 pacts 推到 broker
   └────────────┬───────────┘
                │  (依赖 OK)
                ▼
   ┌────────────────────────┐
   │ provider-verify (job2) │   2. service container 重起 broker(隔离)
   │ 重新 publish → 启 agentcook FastAPI → pact-verifier 校验所有 provider=`agentcook` 契约
   └────────────────────────┘
```

job2 重 publish 是因为 service container 在 job 间不共享(GitHub Actions 设计),重 publish 成本 < 5s,换取每个 job 自包含可调试。

### A 加 spec 后 SOP(每次)

1. A 改 `docs/api/v1.yaml`(加 path / 改 schema 字段)
2. A 同步加/改 `tests/contract/test_01_consumer_*.py`(consumer 端声明新 interaction)
3. A push → `pact-provider-ci.yml` 自动跑
4. job1 PASS = consumer 自洽 + pact 发到 broker;失败通常是 mock 与声明不符 → A 自查
5. job2 PASS = 真 agentcook FastAPI 满足所有声明 contract;失败常见三类:
   - handler 实现与 spec 不一致(A 修 handler)
   - spec 改了但 consumer test 没同步(A 补 test_01_*)
   - excluded path / auth 缺失(检视 `setup_telemetry` 的 `excluded_urls` + 是否需要 JWT)

### Phase 4 上线后的演进(本期不做)

- broker 切外部持久化(共享给跨 repo 团队)
- 接入 `can-i-deploy`(部署前查 broker 验证当前版本兼容性)
- contract publish 带 git tag,实现"contract-as-deployment-gate"

详见 `_internal/L3-strategy/v6-architecture-rationale.md` ADR-007 末段。

---

## Cross-cutting reference

- ADR-007:`_internal/L3-strategy/v6-architecture-rationale.md`
- broker SOP:`_internal/audit/host-setup-guide.md §7`
- 自托管 vs SaaS 决策:`_internal/audit/pact-broker-self-hosting-justification.md`
- Day 11 verify_provider.py CLI:`tests/contract/scripts/verify_provider.py`
