# Phase 5 Day 50 — Performance Report (locust 100u real-qwen + 500u mock + 调优 #1)

**日期**:2026-06-02 · **作者**:Agent C(性能测试 + DevOps,主笔)

> Day 50 = Phase 5 第 2 段。本报告记录 chat 端到端真栈 baseline + 系统极限 + 调优 #1 的实测数据,作为 Day 51 安全/合规 + Phase 5 末 staging 重跑的输入。

---

## TL;DR

- **chat 真栈 100u baseline ✅**:825 reqs / 0 fails / p50=770ms / p95=1900ms / p99=2300ms / RPS 27.73 / qwen 真消耗 ~38K token(预算 5 万的 76%,降时长 60s→30s 守住 80% 阈值)
- **chat mock 200u/500u 极限 ✅**:p95 在 200→500u **平稳 680→690ms**,chat 路径未饱和(0 fail)
- **调优 #1 uvicorn 1→4 workers 保留 ✅**:login fail -95% / login p95 -47% / chat p99 -8%(chat 主链路未达 brief 20% 阈值,但整体改善显著)
- **3 大瓶颈定位**:① uvicorn worker count(已修)② Java :8080 login connection reset @ 500u(D 待修)③ qwen 上游延迟主导 chat 真模式 p99(无法本地修,Phase 5 末 prod 缓存策略)
- **本地真栈 ≠ prod**:建议 Phase 5 末 staging 重跑做最终 baseline,本报告数据用于"相对值"调优判断

---

## §1 本地真栈环境

| 组件 | 版本 / 配置 | 端口 | 备注 |
|------|------------|-----|-----|
| uvicorn | reload mode + 1 worker(原状)/ 调优实验中切 4 worker | :8000 | mock 切换通过 `AGENTCOOK_CHAT_MOCK=true` env(chat.py 每请求 `_use_mock()` 实时读) |
| Java agentcook-api | Spring Boot Tomcat default(threads / accept-count 未调)| :8080 | 健康 `actuator/health: UP` |
| agentcook-app | Vite dev :5174 | :5174 | Day 48 e2e 用 |
| Postgres / Redis / Jaeger / Prometheus / pact-broker | docker(作者管理)| 各自 | 全 healthy |
| locust | 2.44.0(uv 管理 .venv)| - | `uv run locust ...` |
| qwen | qwen-turbo / .env source 后 `AGENTCOOK_LLM_PROVIDER=qwen` | - | duration_ms 实测 658-1082ms |

**Mode 切换关键路径**:
- 真模式:`source .env` → `nohup uv run python -m uvicorn agentcook_app.main:app --host 0.0.0.0 --port 8000 --reload`
- Mock 模式:`AGENTCOOK_CHAT_MOCK=true nohup uv run python -m uvicorn agentcook_app.main:app --host 0.0.0.0 --port 8000` (--reload 与 --workers N 互斥)
- 探测命令:`curl ... | grep '"source":"<provider|mock>"'`

---

## §2 100u 真 qwen baseline(预算守住 80% 阈值)

**实跑命令**:
```bash
uv run locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 30s --headless \
  --csv baseline/chat-100u-real-qwen \
  --html baseline/chat-100u-real-qwen.html \
  ChatUser
```

**协调员代决变更**:run-time 60s → **30s**。理由:5u × 20s 预演实测 0.37 chat/user-second,外推 100u × 60s 约 80K token > 5 万预算 60%。降到 30s 后 ~38K token = 76% 阈值,守住 brief"超 80% 立刻停"。

**实测结果**:

| 指标 | login | chat |
|------|------:|-----:|
| reqs | 100 | **825** |
| fails | 0 | **0** ✅ |
| p50 | 59ms | 770ms |
| p75 | 90ms | 1600ms |
| p95 | 120ms | **1900ms** |
| p99 | 120ms | **2300ms** |
| max | 121ms | 2500ms |
| RPS | 3.36 | **27.73** |

**qwen token 消耗实测**:825 chat × 36 chars output(curl 探测得 `output_chars=36` per chat)≈ 30K output chars + 8K input prompt ≈ **~38K tokens / 76% 预算**(< 80% 阈值 ✅)。

**关键洞察**:
- p50→p95 拉开 2.5x(770→1900ms):qwen-turbo 单次 duration_ms 658-1082ms(curl 5 并发实测),locust 100u 时 qwen 上游开始排队
- 0 fail = qwen 100u 并发未触发 429(免费额度内可承受)
- p99 2.3s 是 qwen 真延迟主导,与 uvicorn / Python 路径无关

---

## §3 200u + 500u mock 系统极限

**实跑命令**(切 mock 后):
```bash
# 200u
uv run locust -f tests/performance/locustfile.py --host http://localhost:8000 \
  --users 200 --spawn-rate 20 --run-time 30s --headless \
  --csv baseline/chat-200u-mock ChatUser

# 500u
uv run locust -f tests/performance/locustfile.py --host http://localhost:8000 \
  --users 500 --spawn-rate 50 --run-time 30s --headless \
  --csv baseline/chat-500u-mock ChatUser
```

**实测结果对照**:

| 指标 | 200u-mock-w1 | 500u-mock-w1 | 趋势 |
|------|------------:|------------:|:----:|
| chat reqs | 1979 | 2623 | +33% |
| chat fail | 0 | **0** ✅ | 平 |
| chat p50 | 620ms | 620ms | **平** |
| chat p95 | 680ms | 690ms | +1% |
| chat p99 | 850ms | 730ms | -14% |
| chat RPS | 66.32 | 87.40 | +32% |
| login reqs | 200 | 253 | +27% |
| **login fail** | 0 | **20 (7.9%)** | 🔴 退化 |
| login p95 | 96ms | **510ms** | 🔴 +431% |

**关键洞察**:
- chat 路径**未饱和** — 200→500u 时 chat p50/p95 几乎平坦(620→620 / 680→690),仅 RPS 增长(mock 单帧 done:true 提前 break,延迟接近 mock generator 固有底线)
- **login 在 500u 突现瓶颈**:20 ConnectionResetError(54)+ p95 510ms(原 96ms),Java :8080 Tomcat / accept-backlog 满
- 系统真极限不在 Python chat,在 **Java auth 入口**

---

## §4 3 大瓶颈识别 + 调优

### 瓶颈 #1:uvicorn 单 worker(已修 ✅,owner C)

**信号**:500u-w1 时 login fail 20(connection reset)+ Python 单 event loop 处理 100 并发 chat + 200 并发 login → uvicorn accept queue 短暂溢出。

**调优**:`--workers 1` → `--workers 4`(--reload 必须移除,二者互斥)。

**重测 500u-mock-w4 vs w1**:

| 指标 | w=1 | w=4 | 改善 | 是否 ≥ brief 20% 阈值 |
|------|----:|----:|-----:|:---------------------:|
| chat p50 | 620ms | 620ms | 0% | ❌ |
| chat p95 | 690ms | 640ms | -7% | ❌ |
| chat p99 | 730ms | 670ms | -8% | ❌ |
| chat max | 800ms | 690ms | -14% | ❌ |
| chat RPS | 87.4 | 84.6 | -3% | ❌ |
| **login p95** | 510ms | 270ms | **-47%** | ✅ |
| **login fail %** | 7.9% | 0.4% | **-95%** | ✅✅ |

**判定**:**保留**。chat 主链路未达 brief 20% 阈值,但 login(系统入口)显著改善,**整体 0 退化**。

**代码改动**:无源码改动。配置改动:启动命令加 `--workers 4` + 移除 `--reload`(prod 环境本来就不带 --reload,这是 dev 限制)。

**生产前提交建议**:Helm `values.yaml` agentCore 加 `extraArgs: ["--workers", "4"]`(Phase 5 末或 staging 重跑前由 A 落 commit)。

### 瓶颈 #2:Java :8080 Tomcat connection backlog @ 500u(待修,owner D)

**信号**:500u-w1 + 500u-w4 都见 login ConnectionResetError(54),uvicorn worker 加到 4 后从 20 → 1 的改善是因为 chat 不再阻塞 accept,但 Java 端的 Tomcat 仍是真瓶颈源。

**根因猜测**(未用 jstack 实测,纯数据推断):
- Spring Boot embedded Tomcat 默认 `server.tomcat.threads.max=200` / `server.tomcat.accept-count=100` — 500u 并发 login 涌入会触发 connection reset
- 或者 HikariCP `maximum-pool-size` 默认 10,大量 login 等待 DB 连接 → 长队列 → Tomcat 反压

**调优建议**(D 领地,Day 50 backlog → Day 51 处理):
- 改 `agentcook-java/agentcook-api/src/main/resources/application.yml`:
  ```yaml
  server:
    tomcat:
      threads:
        max: 400         # default 200
        min-spare: 50    # default 10
      accept-count: 200  # default 100
  spring:
    datasource:
      hikari:
        maximum-pool-size: 30  # default 10
  ```
- D Day 50 已动 Helm `values.yaml` adminBff memory 512Mi → 1Gi(同步可见 cross-cutting,memory `feedback-cross-cutting-flag`),JVM heap 头空间已扩,与本调优互补

### 瓶颈 #3:qwen 上游延迟主导 chat 真模式 p99(本地不可修)

**信号**:100u 真 qwen p50/p95/p99 = 770/1900/2300ms;mock 模式同压力 p99 = 730ms。差值 ≈ 1.6s = qwen 上游 wall-clock。

**根因**:qwen-turbo 首 token + 流式生成 + 网络;免费额度限速也可能拖尾 p99。

**调优建议**(本地不可修,Phase 5 末或 prod buffer):
- A. 缓存层(Redis / SQLite)cache 高频 prompt(教程视频常问问题)→ 减少 qwen 命中率 50%+
- B. 升级 qwen-plus / qwen-max 付费 tier(更稳定 latency,但成本 10x)
- C. local fallback model(ollama qwen2.5:7b)处理 hot prompts,qwen 处理 long-tail

---

## §5 给 Phase 5 buffer / staging 重跑的建议

| 建议 | 何时 | owner |
|------|------|------|
| Helm `values.yaml` agentCore.extraArgs `--workers 4` 落 commit | Phase 5 末或 Day 51 | A |
| Java application.yml Tomcat threads / accept-count / HikariCP 调到推荐值 | Day 51 调优窗口 | D |
| staging 环境 (uvicorn :8000 + Java :8080 + Redis + PG) 起后,**重跑相同 4 档**(100u-real / 200u-mock / 500u-mock / 500u-mock-w4)拿绝对值 baseline | Phase 5 末 / staging 重 stand-up 时 | C(D 配合 Java 调优落实) |
| qwen response cache 设计 + 命中率分析 | Phase 5 末 / Day 53+ | A 主笔 |
| **本地真栈 ≠ staging,本报告数据只用于"相对值"调优判断**(瓶颈在哪一层,优化前后差几倍),不当 prod 数据 | Day 50 起 | C 已 flag 本节 |

---

## §6 旁路诚实交代

### A.brief 60s → 30s 时长降级
按风险信号"超 80% 立刻停",5u × 20s 预演外推 100u × 60s ≈ 80K token,主动降到 30s 守住 76% 阈值。**作者实时授权**(对话 14:10),数据够用。

### B.locust task hung 排错(45 min 时间损失)
- 现象:5u/30u chat task 0 reqs/s 卡死;1u 跑 11 reqs OK
- 根因:`--tags chat` 过滤后 JavaApiUser/PythonSkillUser/SwarmGatewayUser/GrpcChatUser **没匹配 task** 但 locust 仍 instantiate,N user 被均分到这些空 class → spawn 阶段卡住
- 修法:位置参数 `ChatUser` 锁定 user class,放弃 --tags 路径
- 副 finding:现有 PythonSkillUser/SwarmGatewayUser 用 `FastHttpUser.iter_lines()` — FastHttp 不支持,这些 task 从未真跑过(latent bug,Day 50 backlog)

### C.uvicorn restart 丢 .env 事故
- 第一次 restart 没 source .env → uvicorn 走默认 fallback mock(QWEN_API_KEY 缺) → 短暂 ~30s 期间作者前端 chat 走 mock
- 修法:`set -a && source .env && set +a` 后再 nohup → 验证 `metadata.source=provider` + `model=qwen-turbo` 恢复
- 教训:Phase 5 末 staging 启动 doc 必写 .env source 步骤

### D.Helm values.yaml cross-cutting flag(D 同时动)
Day 50 期间观测到 D 改 `deploy/helm/agentcook/values.yaml` adminBff memory 512Mi → 1Gi(JVM heap 头空间扩);本报告 §4 瓶颈 #2 调优建议与 D 互补,Phase 5 末统一落 prod values。

---

## §7 数据资产 MD5

| 文件 | MD5 |
|------|-----|
| `tests/performance/locustfile.py` | `b3d714ba` |
| `tests/performance/baseline/chat-100u-real-qwen_stats.csv` | `08152cb7` |
| `tests/performance/baseline/chat-200u-mock_stats.csv` | `1df12e73` |
| `tests/performance/baseline/chat-500u-mock_stats.csv` | `1ee8807b` |
| `tests/performance/baseline/chat-500u-mock-w4_stats.csv` | `06b4b751` |

`*_stats_history.csv` + `*_failures.csv` + `*.html` 同 baseline/ 目录。

---

**报告完。** 等作者 review 主报告 5 min,Day 50 收尾 → Day 51 brief(合规检查)起草。
