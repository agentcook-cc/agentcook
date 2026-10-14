# agentcook-starter

教程《从 0 到 1 构建商业级 AI Agent 产品》第 22–25 讲的配套项目：保留真实产品的架构形状，砍掉一切可以推迟的东西。

**→ 从 [`python/`](python/README.md) 开始。** 默认 Mock 模式，不需要 API Key：

```bash
git clone https://github.com/agentcook-cc/agentcook.git
cd agentcook/agentcook-starter/python
make setup && make dev   # http://localhost:8000
```

## 和完整版的关系

| 层         | Starter                                          | 完整版 AgentCook                                                |
| ---------- | ------------------------------------------------ | --------------------------------------------------------------- |
| Agent 循环 | 单 Agent ReAct 循环，一个文件（`agent/core.py`） | `agentcook-core`：多 Agent 委派、策略钩子、上下文窗口、并行工具 |
| 模型       | Anthropic SDK + 离线 Mock 模型                   | 多家模型 + 降级链 + 离线 Mock 模型                              |
| 会话       | 进程内存                                         | PostgreSQL（会话、记忆、pgvector）                              |
| 工具       | `BaseTool` + 注册表                              | 工具包、Skill 系统、委派工具                                    |
| 鉴权       | 内测白名单                                       | JWT（与 Java 业务后端共享）                                     |
| 可观测性   | 每请求一行 JSON 日志                             | Prometheus 指标、结构化日志流、运行追踪                         |
| 前端       | 单个 `index.html`                                | React 用户端 + Vue 管理后台                                     |

两边的事件协议是同一个思路（文本增量、工具调用、工具结果、结束），所以从 Starter 毕业到完整版时，前端的心智模型不用变。

## 目录

- [`python/`](python/) — 可运行的项目、测试和第 23/24 讲练习的参考答案（`python/solutions/`）
