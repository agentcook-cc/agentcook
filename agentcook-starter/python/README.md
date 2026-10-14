# AgentCook Starter（Python）

《从 0 到 1 构建商业级 AI Agent 产品》第 22–25 讲的配套项目：一个能跑、能测、能上线的最小 Agent。
默认 **Mock 模式**——不需要 API Key，clone 下来 3 分钟就能对话；ReAct 循环、工具和界面都是真的在跑，只有"模型的判断"由脚本模拟。

## 3 分钟跑起来

```bash
git clone https://github.com/agentcook-cc/agentcook.git
cd agentcook/agentcook-starter/python

make setup   # 创建 .venv、安装依赖、生成 .env（Mock 模式）
make dev     # http://localhost:8000
```

打开 <http://localhost:8000>，试试：

- 搜索一下蓝牙耳机最近有什么热门新品
- 帮我分析一下竞品A的定价策略
- 最近7天哪个商品卖得最好？

你会看到：Agent 先说要查什么 → 工具卡片（点开看输入和结果）→ 基于结果的回答 → 轮数和 token 统计。

没有 `make`？等价命令：

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --port 8000
```

## 接上真实模型

编辑 `.env`：

```bash
MOCK_MODE=false
ANTHROPIC_API_KEY=sk-ant-...
# MODEL_NAME=        # 留空 = 自动选用你的 Key 可用的最新 Sonnet 模型
# ANTHROPIC_BASE_URL= # 可选：任何兼容 Anthropic Messages API 的端点
```

重启 `make dev` 即可。代码不用改：Mock 模型和真实模型走的是同一个循环。

## 项目结构

```
app/
├── main.py              入口：注册路由、挂载前端、CORS、导入工具
├── config.py            所有配置（环境变量 / .env）
├── routers/
│   ├── chat.py          POST /api/chat（SSE）、GET /api/tools、DELETE /api/sessions/{id}
│   └── health.py        GET /health
├── agent/
│   ├── core.py          ReAct 循环：调模型 → 执行工具 → 再调模型 → 回答
│   ├── context.py       会话记忆：每个 session 的消息历史与裁剪
│   ├── prompts.py       System Prompt（人设、工具规则、安全规则）
│   ├── mock_llm.py      离线 Mock 模型（与 Anthropic SDK 接口一致）
│   ├── guard.py         提示词注入的简单拦截（第 25 讲）
│   └── tracing.py       每个请求一行结构化日志（第 25 讲）
├── tools/
│   ├── base.py          BaseTool：name / description / parameters / execute()
│   ├── registry.py      ToolRegistry：注册、查找、导出给模型的工具定义
│   ├── mock_search.py   web_search：搜索（3 套预设结果）
│   └── data_query.py    data_query：只读查询店铺销售数据
└── models/schemas.py    请求/响应模型
frontend/index.html      单文件聊天界面（无构建步骤）
solutions/               第 23、24 讲练习的参考答案（带测试）
tests/                   60 个测试：循环的每个分支、工具、API、真实 SDK 路径
```

## 事件协议

`POST /api/chat`，请求体 `{"message": "...", "session_id": "可选", "user_id": "可选"}`，返回 SSE，每行 `data:` 是一个 JSON 事件，最后是 `data: [DONE]`：

| type          | 字段                                              | 含义                                                           |
| ------------- | ------------------------------------------------- | -------------------------------------------------------------- |
| `text`        | `content`                                         | 回答的一段文字（流式，逐段拼接）                               |
| `tool_call`   | `id`, `name`, `input`                             | 模型要调用的工具                                               |
| `tool_result` | `id`, `name`, `result`, `is_error`, `duration_ms` | 工具执行结果                                                   |
| `done`        | `rounds`, `stop_reason`, `usage`                  | 本轮结束（`stop_reason` 为 `max_rounds` 表示达到推理轮数上限） |
| `error`       | `message`                                         | 本轮失败（会话历史会回滚到这轮之前）                           |

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "你好", "session_id": "test"}'
```

## 加一个工具

1. 新建 `app/tools/weather.py`，继承 `BaseTool`，文件末尾 `tool_registry.register(WeatherTool())`
2. 在 `app/main.py` 的工具导入行加上它：`from app.tools import data_query, mock_search, weather`

完整例子见 `solutions/ch23/weather.py`。想让 Mock 模型也会调用它，给工具加上 `keywords`（触发词）。

## 常用命令

| 命令                        | 作用                                          |
| --------------------------- | --------------------------------------------- |
| `make dev`                  | 开发服务器（自动重载）                        |
| `make test`                 | 跑测试                                        |
| `make lint` / `make format` | 代码检查 / 自动格式化（ruff）                 |
| `make seed`                 | 生成第 24 讲 `sales_query` 用的 SQLite 测试库 |
| `make docker`               | 构建生产镜像                                  |

## 上线

```bash
docker build -t agentcook-starter .
docker run -p 8000:8000 --env-file .env agentcook-starter
```

上线前对照第 25 讲的检查清单：`MOCK_MODE=false`、`ALLOWED_USERS` 内测白名单、`CORS_ORIGINS` 改成你的域名、看 `agent_run` 日志。

会话记忆存在进程内存里（重启即清空，多副本之间不共享）。用户多了以后，把 `app/agent/context.py` 的 `SessionStore` 换成 Redis 或数据库——这正是完整版 [AgentCook](../../README.md) 做的事。
