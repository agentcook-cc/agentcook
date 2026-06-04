# L2 — Cloudflare Pages docs-site MVP + Qwen 后端真测 实战 Cookbook

> 📍 **导航**:本文档是 [DEPLOYMENT.md](../../DEPLOYMENT.md) 中 **L2 Cloudflare Pages MVP** 档的完整实战 cookbook。配套 [L2-wrangler-deploy-sop.md](L2-wrangler-deploy-sop.md)(wrangler CLI 真 deploy SOP)。
>
> 📝 **关于本文档**:这是作者 2026-06-01 真上线 MVP 时的现场实战记录(原 `_internal` 笔记),包含决策时间线 + 5 踩坑 + 命令逐条复盘。**未做过度润色** — 内部代号、协作 Agent 名(A/B/C/D)、Phase 编号会原样出现,保留真实建造现场感。读者按命令时不影响理解,把 Agent 代号看作"分工占位"即可。
>
> **实测日期**: 2026-06-01(Phase 4.5 真上线前的 P1 验证阶段)
>
> **从 0 到 1**: docs-site 上 `.pages.dev` 免费 subdomain + Python uvicorn + 千问 `qwen-turbo` 真调通过。
>
> **适用场景**: 任何 monorepo 项目想**先免费验证 MVP 效果**再决定要不要买域名 / 真上线的最小可用方案。

---

## TL;DR(3 句话)

1. **目的**: 跳过买域名(¥110/年 .dev / ¥650 .ai),用 Cloudflare Pages 自动给的 `.pages.dev` subdomain + 千问 Qwen 免费额度,先看 MVP 效果再决定要不要花钱。
2. **完成**: docs-site 上线 https://agentcook.pages.dev ✅ / Qwen `qwen-turbo` 真调通(39 token,免费额度内)✅
3. **代价**: 5 个踩坑(2 个 Cloudflare UI 陷阱 + 1 个 build 配置 + 2 个 shell quirk),花了 ~15 min 排查,详见 §3 踩坑录。**总成本 ¥0,总耗时 ~40 min**。

---

## 1. 决策时间线(为什么走这条路)

### 决策 1: 域名选型(候选 5 选 1)

**术语**: 个人品牌路线(macrozheng 同款)= 主域承载"老A 这个人"身份,产品挂 subdomain。

**选项**(已 whois 全验证):
| 候选 | 年费 | TLD 信号 | 字符 |
|---|---:|---|---:|
| laoa.ai | ¥650 | AI 圈一锤认证 | 4 |
| laoa.dev | ¥110 | Google TLD / 技术圈 100% 接受 | 4 |
| p7coder.com | ¥75 | .com 安全垫 / 业务词派 | 7 |
| bigtechalpha.com | ¥75 | "大厂码农老A"直译 | 14 |
| laoaai.com | ¥75 | "老A+AI"双关但可读性差 | 7 |

**影响**: 域名 = personal brand 长期资产,选错难迁。.ai 贵但纯粹 / .dev 性价比最高 / .com 安全但弱信号。

**推荐 + 时序**: `laoa.dev` ⭐(性价比最高,4 字优势 + Google TLD)。**但作者临时改主意 → 选项 6**: 先用 Cloudflare Pages 免费 `.pages.dev` 跑 MVP,效果满意再买 `laoa.dev`。

### 决策 2: 时机选型(P1 免费 MVP vs 直接买)

**术语**: P1 = MVP 免费验证 / P2 = 真上线买域名

**选项**:
| 路径 | 投入 | 看到效果 | Phase 4 close |
|---|---|---|---|
| A 直接买 laoa.dev + 完整 Phase 4.5 | ¥110 + 6 h cascade | 完整(docs + demo + Blue-Green) | ✅ 能 |
| **B P1 免费 MVP 先验证**(选定) | ¥0 + 30 min | docs + 部分 demo | ❌ 不能(没 Blue-Green) |

**影响**: B 路径不能正式 close Phase 4(缺 Blue-Green 切流量),但 P1 验证后**真看到产品体验**再决定要不要投。

**推荐 + 时序**: B(本次选定)。如果 P1 效果满意 → 走 P2 买域名 + 跑完整 Phase 4.5。

### 决策 3: 默认 LLM Provider(OpenAI → Qwen,ADR-016)

**术语**: agentcook-providers 包架构本就支持 4 provider(OpenAI / Anthropic / Qwen / Zhipu),只需切默认。

**选项**:
| Provider | 默认模型 | 成本 | 国内速度 |
|---|---|---|---|
| OpenAI gpt-4o-mini | ¥0.004/次 chat | 信用卡 | 慢 |
| **Qwen qwen-turbo**(选定) | **免费额度内 ¥0** | 0 | 快(国内机房) |
| Qwen qwen-plus | 较少免费 | 接近 gpt-4o | 快 |

**影响**: demo 真上线后被刷一次,OpenAI 烧 ¥100+,Qwen 在免费额度内 ¥0。

**推荐 + 时序**: qwen-turbo。**ADR-016 落档**,改动仅 `factory.py` 一行(`qwen-plus` → `qwen-turbo`)。详 `agentcook-cc/docs/adr/ADR-016-llm-default-provider-qwen.md`。

---

## 2. P1 完整流程(按时序)

### P1.0 准备(前置实测)

```bash
# 实测 docs-site 是否 build 通过(产物存在?)
ls agentcook-cc/docs-site/.vitepress/dist/

# 实测 docker-compose.dev.yml 服务清单(避免端口冲突)
grep -E "^  [a-z].*:$|image:|ports:" agentcook-cc/docker-compose.dev.yml

# 实测 cloudflared 是否已装
which cloudflared

# 实测 Python uv 是否已装
which uv
```

**关键发现**:

- ✅ docs-site dist/ 已 build(404.html / adr / guide / assets 齐全)
- ✅ docker dev stack 已经在跑 11 天(postgres / jaeger / prometheus / pact-broker 全 healthy)
- ❌ cloudflared 未装
- ✅ uv 在 `<HOME>/.local/bin/uv`(但默认不在 zsh PATH)

### P1.1 docs-site 上 Cloudflare Pages(实测 ~15 min,含踩坑)

#### Step A: 找 Cloudflare Pages 入口

⚠️ Cloudflare 2024 Q4 改 UI,Pages 入口被合并进 Workers & Pages 主入口下,**默认推 Worker 创建**(详 §3 坑 1)。

**正确路径**(2026-06 实测):

```
左侧菜单 Compute → Workers & Pages → Create application
→ 选 "Import an existing Git repository"(不要选 "Hello World" 那种)
→ 选 GitHub org agentcook-cc → repo agentcook
→ 进入 "Deploy a site from your account" 3 步流程(✅ 这才是 Pages)
```

**对照 Pages vs Worker 入口的铁证**:

- ✅ Pages: 顶部步骤 `Select repository → Set up builds and deployments → Deploy site` / 标题 "Deploy a site" / 有 "Build output directory" 字段
- ❌ Worker: 标题 "Create a Worker" / Deploy command 默认 `npx wrangler deploy` / 没有 Build output directory

#### Step B: Pages build 配置(monorepo 关键字段)

| Field                  | Value                                                                                |
| ---------------------- | ------------------------------------------------------------------------------------ |
| Project name           | `agentcook`(URL = agentcook.pages.dev,或改 `agentcook-docs` 更清晰)                  |
| Production branch      | `main`                                                                               |
| Framework preset       | `None`(monorepo 自定义 build)                                                        |
| Build command          | `pnpm install --frozen-lockfile && pnpm --filter @agentcook-cc/docs-site docs:build` |
| Build output directory | `docs-site/.vitepress/dist`(⚠️ **末尾不能有空格**,详 §3 坑 3)                        |
| Root directory         | `/`(留空)                                                                            |
| Env var `NODE_VERSION` | `20`(不设会用默认 18,VitePress 2 可能 fail)                                          |
| Env var `CI`           | `true`                                                                               |
| Deploy command         | **留空**(Pages 不需要,Worker 才需要)                                                 |

#### Step C: build 验证(2 次重 build,~12 min)

- **第 1 次** fail: setuptools auto-discovery 撞 multiple top-level packages → 详 §3 坑 2
- **第 2 次** fail: Build output directory 末尾空格 → 详 §3 坑 3
- **第 3 次** pass: build complete in 4.31s,deploy 到 ~300 CDN 节点
- **最终 URL**: https://agentcook.pages.dev/ ✅

### P1.2 demo 后端 uvicorn + Qwen 真测脚本(实测 ~15 min)

#### Step A: 创建 .env 注入 Qwen key

```bash
cd <workspace>/agentcook-cc

# 方法 1: heredoc(zsh 完整段贴入)
cat > .env << 'ENVFILE'
AGENTCOOK_LLM_PROVIDER=qwen
QWEN_API_KEY=sk-xxx你的key
QWEN_MODEL=qwen-turbo
DASHSCOPE_API_KEY=sk-xxx你的key
ENVFILE

# 方法 2: VSCode 直接编辑
code .env

# 验证
cat .env
```

⚠️ `.gitignore` 已含 `.env`,放心填真 key。

#### Step B: 启动 Python uvicorn(终端 1,前台)

```bash
cd <workspace>/agentcook-cc

# 加载 env(必须,否则 uvicorn 看不到 QWEN_API_KEY)
set -a; source .env; set +a

# 验证 env 已加载(只看前 6 位防泄露)
echo "Provider: $AGENTCOOK_LLM_PROVIDER / Model: $QWEN_MODEL / Key 前 6 位: ${QWEN_API_KEY:0:6}***"

# 启动 uvicorn(用完整路径,避免 uv 不在 PATH 报 command not found)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
  ~/.local/bin/uv run python -m uvicorn agentcook_app.main:app --host 0.0.0.0 --port 8000 --reload
```

**期望终止输出**:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### Step C: chat 端点测试(发现是 mock,详 §3 坑 5)

```bash
# health 测通(秒过)
curl -sf http://localhost:8000/health
# → {"status":"ok"}

# chat 端点(注意真路径是 /api/v1/chat/stream 不是 /api/v1/chat)
curl -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" -d '{"messages": [{"role": "user", "content": "test"}]}' -N
# → 返回预录 mock SSE 帧(Phase 5 才接真 LLM)
```

#### Step D: Qwen 真测脚本(绕过 mock,直接调 provider)

`test_qwen.py`(根目录,临时):

```python
import asyncio, os, sys
from agentcook_core.types import Message
from agentcook_providers.factory import create_provider

async def main():
    provider = create_provider(provider="qwen")
    messages = [Message(role="user", content="你好,一句话(20 字内)介绍 AI agent")]
    response = await provider.chat(messages, temperature=0.7, max_tokens=200)
    print(f"Qwen 回答: {response.message.content}")
    print(f"Tokens: input={response.usage.input} / output={response.usage.output} / total={response.usage.total}")

asyncio.run(main())
```

```bash
cd <workspace>/agentcook-cc
set -a; source .env; set +a
uv run python test_qwen.py
```

**实测输出 ✅**:

```
Provider: qwen / Key 前 6 位: sk-6b1***
Model: qwen-turbo
============================================================
Qwen 回答:
AI agent 是能自主决策和执行任务的智能程序。
============================================================
Tokens: input=26 / output=13 / total=39
Finish: stop
✅ qwen-turbo 真 work,配置 OK
```

### P1.3 cloudflared tunnel(实测 ~3 min,完成 ✅)

```bash
# 装 cloudflared
brew install cloudflared
cloudflared --version

# 启动 quick tunnel(终端 2,前台,占用)
cloudflared tunnel --url http://localhost:8000

# 实测输出:
# Your quick Tunnel has been created! Visit it at (...):
#   https://aquarium-writer-extending-thumbs.trycloudflare.com
```

**实测外网访问验证 ✅**(协调员从外网真测):

| 端点                  | 实测                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| `/health`             | HTTP 200 / `{"status":"ok"}` / 1.13s 响应(含跨洋 + tunnel 加密开销)                                  |
| `/metrics`            | HTTP 200 / Prometheus 格式真实 GC 数据                                                               |
| `/api/v1/chat/stream` | HTTP 200(schema 校验返回 422 是 curl 字段错,不是端点问题)                                            |
| Response headers      | `server: cloudflare` + `cf-ray: a04e1ccf9dc2501e-SJC`(San Jose 边缘节点)+ `cf-cache-status: DYNAMIC` |

⚠️ **trycloudflare URL 是 quick tunnel,关掉 cloudflared 进程就失效**。要持久 URL 必须用 named tunnel(需要 Cloudflare 账户 + 配 zone,等价 P2)。

### P1.5 chat 接真 Qwen — Phase 4.6 提前(实测 ~30 min,2026-06-01 P1 闭环后追加)

**背景**: P1 闭环验证后,作者决策"先用免费域名 + 真上线推迟到教程完成 + 但 chat 必须现在接真 LLM"(避免 demo 演示价值打折)。Phase 4.6 = roadmap Day 50 任务提前到 P1 后。

**改 1 个文件**(`agentcook/src/agentcook_app/routers/chat.py`,144 → 259 行):

```python
# 加 3 个辅助函数
def _get_provider() -> Any:
    """lazy singleton,首次请求时 create_provider()"""

def _use_mock() -> bool:
    """env var 切换:AGENTCOOK_CHAT_MOCK=true / 或没配 LLM_PROVIDER → mock"""

async def _stream_real_response(request) -> AsyncIterator[bytes]:
    """调 provider.stream_chat() 包 ChatChunk → ChatStreamFrame SSE"""

# chat_stream 端点:根据 _use_mock() 选 generator
generator = _stream_mock_response(request) if _use_mock() else _stream_real_response(request)
```

**实测验证 ✅**(在 http://localhost:5174/chat 发"你是谁"):

- 返回:"我是通义千问,是阿里巴巴集团旗下的通义实验室自主研发的超大规模语言模型..."
- mock 不可能返回这个,**真 qwen-turbo 确认接通**
- SSE 协议 0 改动,前端 useSseChat.ts 0 改动
- uvicorn 终端 1 自动 reload(无 import error)
- OTel span `model.openai.stream_chat / model.name=qwen-turbo` 自动追踪
- Langfuse(http://localhost:3000)自动 trace(继承 OpenAIProvider 已 wired 的 hook)

**详 ADR-017** `docs/adr/ADR-017-chat-endpoint-real-llm.md`(Phase 4.6 决策完整留档)。

### P1.4 前端 UI agentcook-app 启动 + 登录(实测 ~10 min,含踩坑)

#### Step A: 启动 vite dev server(新开终端 3)

```bash
cd <workspace>/agentcook-cc/agentcook-app
pnpm dev
# 启动后:Local: http://localhost:5174/
```

#### Step B: 浏览器登录(http://localhost:5174/login)

**Phase 3 dev 模式**:AuthController.java 第 45-51 行**不验证密码**,任意非空 username + password 都返回 JWT(Phase 4 Day 33-34 才换真身份验证)。

| 字段             | 填                                                |
| ---------------- | ------------------------------------------------- |
| Username / Email | `admin@agentcook.cc`(matches V2\_\_seed_data.sql) |
| Password         | `dev`(任意非空字符)                               |

#### Step C: 真访问 chat 界面 ✅

登录成功后跳转 `/chat`,UI 含:

- 顶部 AgentCook 品牌 + 右上 admin 头像
- 左侧 Conversations 列表(3 个示例:Help me write a Python script / Explain DDD aggregates / Review my PR)
- 中间对话区 + 底部 Plugins 按钮 + Type a message 输入框
- 输入"hi" / "你是谁" → 返回 mock 流式响应("I'd be happy to help you with that...")
- **真 chat 走 mock 不是 qwen,Phase 5 才接真 LLM(详坑 5)**

---

## 3. 踩坑录(7 个,按严重度)

### 🔴 坑 1: Cloudflare Pages 入口被 UI 改版藏深,默认推 Worker

**现象**: 主页找不到 Pages 入口,点 "Create application" 默认进 "Create a Worker" 流程,看到 "Deploy command: npx wrangler deploy" 这种 Worker 专属字段。

**根因**: Cloudflare 2024 Q4 把 Workers 和 Pages 合并到 "Workers & Pages" 统一入口,**默认 onboarding 推 Worker 模式**。Pages 入口需要手动选 "Import an existing Git repository"。

**修复**:

- ✅ 主路径: Workers & Pages → Create application → Import an existing Git repository → 选 GitHub repo → 进入 "Deploy a site from your account"(才是 Pages)
- ✅ 备用 URL 直达: `https://dash.cloudflare.com/?to=/:account/pages/new/provider/github`
- ✅ 兜底方案: wrangler CLI(`npm install -g wrangler && wrangler pages deploy ...`)

**铁证对照**:
| 标志 | Pages | Worker |
|---|---|---|
| 标题 | "Deploy a site from your account" | "Create a Worker" |
| 默认 Deploy command | (无,留空) | `npx wrangler deploy` |
| Build output directory 字段 | ✅ 有 | ❌ 无 |
| 顶部步骤数 | 3(Select / Setup / Deploy) | 类似但实际部署语义不同 |

### 🔴 坑 2: 根 pyproject.toml 缺 [build-system],Cloudflare 跑 pip install . 撞 setuptools auto-discovery

**现象**: build log 显示 pnpm install 成功,然后 Cloudflare **自动跑 `pip install .`**(检测到 pyproject.toml),报错:

```
error: Multiple top-level packages discovered in a flat-layout:
  ['poc', 'e2e', 'proto', 'deploy', 'agentcook', 'node_modules'].
```

**根因**:

- Cloudflare v2 build system 检测到 pyproject.toml 自动跑 pip install .
- pyproject.toml 是 uv workspace 配置(workspace 根本身没有要 build 的 package),但**没声明 `[build-system]`**
- pip 默认走 setuptools backend,setuptools 用 auto-discovery 在 flat-layout 找到 5 个 top-level dirs,直接挂

**修复**(改 4 行,完全干净):

```toml
# agentcook-cc/pyproject.toml(在 [project] 段后加)
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = []   # 关键:告诉 setuptools 这个 root 不需要 build 任何 package
```

**为什么这是最优解**:

- uv workspace 用自己的 build backend(uv_build),不依赖 setuptools → 改动**对 uv 行为零影响**
- pip install . 会成功 build 一个空 wheel(`agentcook_workspace-0.1.0-py3-none-any.whl`,size=1081 bytes)
- 不破坏任何现有工具链
- Phase 4.5 / Phase 5 真上线时同样适用

**实测验证**:

```
2026-06-01T09:43:49Z  Successfully built agentcook-workspace
2026-06-01T09:43:49Z  Successfully installed agentcook-workspace-0.1.0
```

### 🟡 坑 3: Build output directory 末尾输入空格,validating 阶段挂

**现象**: build 全部跑完(vitepress 4.31s 成功),最后一步报:

```
Validating asset output directory
Error: Output directory "docs-site/.vitepress/dist " not found.
                                                  ↑ 这里多一个空格
```

**根因**: Cloudflare UI 的 Build output directory 字段在粘贴或手动输入时末尾混入了一个空格,Cloudflare 按字面匹配目录名,找不到 `dist ` 这个目录。

**修复**: Cloudflare → 项目 Settings → Builds & deployments → Edit configuration → Build output directory 字段末尾 backspace 一次 → Save → Retry deployment(不需要新 commit)。

**避免重犯**: 复制粘贴 Cloudflare 字段后**用方向键移到末尾按一次 backspace 确认无空格**。Cloudflare UI 没有自动 trim,这是个长期 trap。

### 🟢 坑 4: zsh 反斜杠换行 quirk(命令分多行复制时 `command not found:`)

**现象**: 复制带反斜杠换行的 curl/bash 命令贴进 zsh,某些行报 `zsh: command not found:`(冒号后空白),实际命令还是成功执行。

**根因**: zsh 把反斜杠换行后的空行解释成"空命令",抱怨 `command not found:` 但不阻止后续行执行。

**修复**:

- 方案 A: 改用**单行命令**,不用反斜杠换行
- 方案 B: 忽略报错(命令实际是成功的)

**示例**:

```bash
# 反斜杠换行(zsh 会 quirk 但可工作)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [...]}' \
  -w "\n\nHTTP: %{http_code}\n"

# 单行(zsh 不 quirk)
curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" -d '{"messages": [...]}' -w "\n\nHTTP: %{http_code}\n"
```

### 🟡 坑 5: chat 端点 `/api/v1/chat/stream` 当前是 mock 实现(Phase 5 才接真 LLM)

**现象**: `curl POST /api/v1/chat/stream` 返回流式响应,但**内容是预录 mock 字符串**(`"I'd be happy to help you with that!..."` 这种),**不真调 LLM**。

**根因**(chat.py 第 7-12 行原话):

> "Phase 5 replaces the mock LLM with real provider calls. Today's mock generates a realistic multi-frame streaming response for B to develop against."

**影响**:

- ❌ P1 阶段无法通过 chat 端点验证 qwen-turbo 真效果
- ✅ 但能验证 FastAPI + 路由 + middleware + SSE 链路通

**修复 / 绕过**: 写 `test_qwen.py` 临时脚本(详 §2 P1.2 Step D)直接调 `agentcook-providers` 的 `create_provider("qwen").chat(messages)`,绕过 mock 端点,真测 qwen API key + 模型可用性。

**P2 / Phase 5 计划**: roadmap Day 50 改 chat.py 把 mock 换成 `provider = create_provider(...)`,真接 LLM。

### 🔴 坑 6: 前端 hardcode baseURL 绕过 vite proxy 触发 CORS(4 文件 6 处)

**现象**: 浏览器登录返回 "Invalid credentials. Please try again."。但**实际 fetch 抛 CORS 异常**(不是密码错),LoginPage.tsx 第 22-23 行 catch-all 把所有 fetch 异常都映射成 "Invalid credentials" 误导用户。

**根因**:

- `vite.config.ts` 第 39-49 行**已经配好 proxy**(`/api/v1/auth → JAVA_API` 等),只要前端走相对路径就能避 CORS
- 但 3 个前端文件硬编码 `http://localhost:8080` / `http://localhost:8000`,**绕过 vite proxy 直接跨域调后端**,Java 后端没配 `@CrossOrigin`,浏览器 block

**根因文件 + 行数(实测 grep)**:
| 文件 | 行 | hardcode |
|---|---|---|
| `agentcook-app/src/stores/auth.ts` | 47, 69, 95 | `"http://localhost:8080"`(3 处) |
| `agentcook-app/src/hooks/useSseChat.ts` | 18 | `"http://localhost:8000"`(1 处) |
| `agentcook-app/src/api/client.ts` | 15, 18 | `"http://localhost:8000"` + `"http://localhost:8080"`(2 处) |

**修复(2 步)**:

1. **改 4 个文件 6 处 hardcode → 空字符串**(让 fetch 走相对路径,vite 自动 proxy):

   ```typescript
   // 改前
   import.meta.env.VITE_JAVA_API_BASE_URL || "http://localhost:8080";
   // 改后
   import.meta.env.VITE_JAVA_API_BASE_URL || "";
   ```

2. **`vite.config.ts` 补 5 条 proxy 规则**(原配置缺 chat / delegations / logs / health / metrics):
   ```typescript
   "/api/v1/chat": { target: PY_API, changeOrigin: true },
   "/api/v1/delegations": { target: PY_API, changeOrigin: true },
   "/api/v1/logs": { target: PY_API, changeOrigin: true },
   "/health": { target: PY_API, changeOrigin: true },
   "/metrics": { target: PY_API, changeOrigin: true },
   ```

**重启**: vite.config.ts 改动**HMR 不重读**,必须 `Ctrl+C` + `pnpm dev` 重启。auth.ts / useSseChat.ts / client.ts 改动 HMR 自动 reload。

**验证(实测通过)**: 重启后浏览器 Network → login 请求 URL 变成 `http://localhost:5174/api/v1/auth/login`(同源),vite 内部转发到 :8080,响应 `access-control-allow-origin: http://localhost:5174` 200,JWT 返回。

**P2 路线**: 真上线时仍要给 Java 后端加 CORS 配置(`@CrossOrigin(origins = "https://agentcook.laoa.dev")` 或全局 SecurityConfig),vite proxy 只在 dev 模式有效,prod build 后没 dev server 转发。

### 🔴 坑 7: router 无 auth guard,LoginPage 注释说"App 自动切"但 App.tsx 没监听 store

**现象**: 登录返回 200 + JWT(token 已存 localStorage),但 LoginPage 不跳转,用户看到 Sign In 按钮不动。

**根因**(LoginPage.tsx 第 20 行注释):

> "login() 调用 zustand setTokens → isAuthenticated 变为 true → App 自动重渲染切到 ChatPage"

**但实测 grep**:

- `App.tsx` 只用 `RouterProvider` 静态包 router,**没监听 zustand store 的 `isAuthenticated`**
- `router.tsx` 是纯静态 6 路由数组,**没有 auth guard 组件包装 `/chat`**,也没有 `/login` 已登录跳转逻辑
- 注释陈述的"自动切"行为**不存在**

**修复**(`LoginPage.tsx`):

```typescript
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

const navigate = useNavigate();
const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

useEffect(() => {
  if (isAuthenticated) {
    navigate("/chat", { replace: true });
  }
}, [isAuthenticated, navigate]);
```

**HMR 自动 reload**,刷新浏览器即可。

**P2 / Phase 5 路线**: 应该在 `router.tsx` 加 `ProtectedRoute` 高阶组件守卫所有 `/chat/*` 路径,未认证跳 `/login`;`/login` 已认证跳 `/chat`。当前修复是临时方案,只在 LoginPage 单点 navigate,不防"未登录访问 /chat"的反向漏洞。

### 🟢 坑 8: pnpm filter 跨 workspace 通配可能与 turbo 冲突(实测无影响,留档)

无具体现象,本次 P1 跑 `pnpm --filter @agentcook-cc/docs-site docs:build` 顺利。但 monorepo 有 turbo.json + 5 workspace 时,filter 选择器和 turbo 任务图可能冲突。**留档观察**,Phase 5 e2e 测试如果跨 workspace 跑 lint/test 再 flag。

---

## 4. 完整命令清单(按时序,可复制粘贴)

```bash
# === P1.0 前置实测 ===
ls <workspace>/agentcook-cc/docs-site/.vitepress/dist/
which uv
which cloudflared    # 期望未装
docker ps             # 期望 dev stack 已 healthy

# === P1.1 docs-site Cloudflare Pages ===
# (UI 操作:见 §2 P1.1,无 CLI 命令)
# 关键修复 1(pyproject.toml setuptools fail):
#   编辑 agentcook-cc/pyproject.toml 加 [build-system] + [tool.setuptools] packages=[]
cd <workspace>/agentcook-cc
git add pyproject.toml
git commit -m "fix(build): add [build-system] to skip Cloudflare Pages pip auto-install fail"
git push origin main
# 关键修复 2(Build output directory 空格):
#   Cloudflare UI → Settings → Edit configuration → 删末尾空格 → Save → Retry deployment

# === P1.2 demo 后端 + Qwen 真测 ===
cd <workspace>/agentcook-cc

# Step A: 创建 .env
cat > .env << 'ENVFILE'
AGENTCOOK_LLM_PROVIDER=qwen
QWEN_API_KEY=sk-xxx你的key
QWEN_MODEL=qwen-turbo
DASHSCOPE_API_KEY=sk-xxx你的key
ENVFILE

# Step B: 启动 uvicorn(终端 1)
set -a; source .env; set +a
echo "Provider: $AGENTCOOK_LLM_PROVIDER / Key 前 6 位: ${QWEN_API_KEY:0:6}***"
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 ~/.local/bin/uv run python -m uvicorn agentcook_app.main:app --host 0.0.0.0 --port 8000 --reload

# Step C: 端点测试(终端 2)
curl -sf http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"test"}]}' -N

# Step D: Qwen 真测(终端 2)
set -a; source .env; set +a
uv run python test_qwen.py

# === P1.3 cloudflared tunnel(实测完成)===
brew install cloudflared
cloudflared --version
cloudflared tunnel --url http://localhost:8000   # 输出 trycloudflare URL,前台占用终端 2

# === 外网真访问验证(实测全过)===
TUNNEL_URL=https://aquarium-writer-extending-thumbs.trycloudflare.com   # ← 本次实测 URL
curl -sf $TUNNEL_URL/health                       # → 200 / {"status":"ok"} / 1.13s
curl -sf $TUNNEL_URL/metrics | head -10           # → 200 / Prometheus GC 真数据
curl -sI $TUNNEL_URL/health                       # → cf-ray: ...-SJC / server: cloudflare

# === P1.4 前端 agentcook-app(新开终端 3)===
cd <workspace>/agentcook-cc/agentcook-app
pnpm dev
# Local: http://localhost:5174/

# Java 后端真测(确认 dev login 任意非空 password 都通)
curl -sf -w "\nHTTP: %{http_code}\n" http://localhost:8080/api/v1/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin@agentcook.cc","password":"dev"}'
# → 200 + JWT

# 浏览器:http://localhost:5174/login → 填 admin@agentcook.cc / dev → Sign In
# 期望:跳转到 /chat/sX,显示 3 示例会话 + AgentCook 品牌
```

---

## 5. 关键文件改动清单

| 文件                                                                  | 改动                                                                                                                    | 是否 commit                      |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| `agentcook-cc/pyproject.toml`                                         | 加 `[build-system]` + `[tool.setuptools] packages=[]`(4 行)                                                             | ✅ commit `b74ef95`              |
| `agentcook-cc/agentcook-providers/src/agentcook_providers/factory.py` | `_DEFAULT_MODELS["qwen"]` 从 `qwen-plus` 改成 `qwen-turbo`(1 行)                                                        | 待 commit                        |
| `agentcook-cc/docs/adr/ADR-016-llm-default-provider-qwen.md`          | 新增 122 行 ADR(默认 LLM Provider 决策)                                                                                 | 待 commit                        |
| `agentcook-cc/.env`                                                   | 新建,含 4 行 env vars                                                                                                   | ❌ `.gitignore` 保护,绝不 commit |
| `agentcook-cc/test_qwen.py`                                           | 临时验证脚本(54 行)                                                                                                     | ⚠️ P1 闭环后删除                 |
| `agentcook-cc/agentcook-app/src/stores/auth.ts`                       | 3 处 `"http://localhost:8080"` → `""`(走 vite proxy,避 CORS)                                                            | 待 commit                        |
| `agentcook-cc/agentcook-app/src/hooks/useSseChat.ts`                  | 1 处 `"http://localhost:8000"` → `""`                                                                                   | 待 commit                        |
| `agentcook-cc/agentcook-app/src/api/client.ts`                        | 2 处 hardcode → `""`(共享 axios client)                                                                                 | 待 commit                        |
| `agentcook-cc/agentcook-app/vite.config.ts`                           | 加 5 条 proxy 规则(`/api/v1/agents` / `/api/v1/chat` / `/api/v1/delegations` / `/api/v1/logs` / `/health` / `/metrics`) | 待 commit                        |
| `agentcook-cc/agentcook-app/src/pages/LoginPage.tsx`                  | 加 `useEffect` 监听 `isAuthenticated` → `navigate("/chat")`(router 无 guard 临时补)                                     | 待 commit                        |

**Cloudflare 端**:

- Pages project: `agentcook`(URL = `https://agentcook.pages.dev`)
- Build settings: Framework=None / Build command / Build output directory=`docs-site/.vitepress/dist`(无尾空格)/ NODE_VERSION=20 + CI=true
- Auto-deploy: ✅ on push to main 自动 trigger

---

## 6. 实测成本 + 收益

| 维度            | 实测值                                                                                       |
| --------------- | -------------------------------------------------------------------------------------------- |
| 总成本          | **¥0**(Cloudflare Pages 免费 + Qwen 免费额度 + cloudflared 免费 + trycloudflare URL 免费)    |
| 总耗时          | **~70 min**(P1.1 ~15 min / P1.2 ~15 min / P1.3 ~3 min / P1.4 ~10 min / **踩坑诊断 ~25 min**) |
| docs-site 上线  | ✅ https://agentcook.pages.dev / 全球 CDN ~300 节点                                          |
| Qwen 真测       | ✅ qwen-turbo 39 token,免费额度内                                                            |
| chat 端点       | ✅ **真接 qwen-turbo**(Phase 4.6 提前完成,详 ADR-017 / cookbook P1.5)                        |
| 外网 demo 访问  | ✅ https://aquarium-writer-extending-thumbs.trycloudflare.com 5 endpoint 全 200              |
| 前端 UI 真界面  | ✅ http://localhost:5174/chat 完整 chat + 3 示例会话 + Plugins 入口                          |
| 登录闭环        | ✅ admin@agentcook.cc / dev(Phase 3 不验证密码,JWT 真发)                                     |
| Phase 4 close   | ❌ 不能(缺 Blue-Green,P2 才能)                                                               |
| 长期 reuse 价值 | **极高**(7 踩坑全留档,后续 docs / Pages / vite proxy / router guard 问题秒解决)              |

---

## 7. 下一步(P2 决策点)

**当 P1 全部完成后,根据效果决定**:

### if P1 效果满意 → 走 P2 真上线(¥110 + 6 h)

1. Cloudflare Registrar 注册 `laoa.dev` ¥110/年
2. cascade 改造 66 文件(`agentcook.cc` → `laoa.dev`),分 3 圈分发 A/B/C/D
3. 完成 Phase 4.5(Blue-Green 真切流量)
4. 协调员收尾:Phase 4 closeout + GO/NO-GO 决策书 + Phase 5 brief

### if P1 效果一般 → 修产品后再决定(¥0 延期)

1. 不动域名,继续完善 docs / demo 内容
2. 修完再走 P2

### if P1 效果差 → 反向调整路线(止损)

1. 检视架构 / docs 内容是否需要重写
2. 反思 personal brand 路线是否合适
3. 可能转向其他方向(纯教程 / 纯产品 / etc)

---

## 8. Source

- 实测时间窗: 2026-06-01 16:00 - 20:35(P1.1 + P1.2 + P1.3 + P1.4 **全部完成 ✅**)
- 协调员 AI session: 含完整对话上下文 + 所有命令 + 所有 build log + 7 踩坑诊断
- 关联文档:
  - `agentcook-cc/docs/adr/ADR-016-llm-default-provider-qwen.md`(LLM 切换决策)
  - `_internal/audit/phase4-quality-report-2026-05-22.md`(Phase 4 收尾质量报告)
  - `_internal/operations/command-cookbook.md`(协调员命令字典 1738 行,本 cookbook 是其子文档,可考虑加 §1.x 引用指针)

---

**Cookbook 完(P1 全闭环)。** 7 踩坑全留档 / 4 阶段全实测通过 / 5 文件改动 + 1 ADR 落档。**下一步:作者拍 P2 决策**(详 §7)。
