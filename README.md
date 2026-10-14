# AgentCook

**开源的商业级 AI Agent 产品**：一个会用工具、会委派专家、能记住用户、可以直接上线的 Agent，加上把它跑起来所需的整套工程——运行时、业务后端、用户端、管理后台、部署和测试。

> 配套教程《从 0 到 1 构建商业级 AI Agent 产品》：[agentcook-tutorial](https://github.com/agentcook-cc/agentcook-tutorial)。
> 想先读一个 1000 行以内的最小版本？看 [`agentcook-starter/python`](agentcook-starter/python/README.md)。

## 5 分钟跑起来（不需要 API Key）

```bash
uv sync --all-packages --all-extras --group dev   # Python 依赖
pnpm install                                       # 前端依赖

make run    # 终端 1：Agent 运行时 http://localhost:8000（离线 Mock 模型，内存存储）
make web    # 终端 2：聊天界面   http://localhost:5174
```

打开 <http://localhost:5174>，试试：

- `calculate 1299 * 0.85 - 50` —— 看 Agent 调用计算器工具，结果卡片可以展开
- `please ask the analyst to review our sales` —— 看主 Agent 把任务委派给「数据分析师」
- 回复生成中点「停止」—— 服务端的运行被真正取消，已生成的部分保留

Mock 模型说的是和真实模型一样的接口，所以你看到的工具调用、委派、流式输出、会话持久化全部是真实代码在跑。
接上真实模型只需要环境变量：

```bash
AGENTCOOK_LLM_PROVIDER=qwen,zhipu,mock DASHSCOPE_API_KEY=... make run   # 通义千问，失败降级到智谱，再降级到 Mock
```

## 它由什么组成

```
                       ┌──────────────── agentcook-app (React) ── 用户聊天
 浏览器 ───────────────┤
                       └──────────────── agentcook-admin (Vue) ── 运营后台
          │ /api/v1/chat, conversations, agents, skills…      │ /api/v1/auth, users, quota…
          ▼                                                    ▼
 agentcook (FastAPI 运行时)  ◄── JWT（同一密钥）──  agentcook-java (Spring Boot)
   Agent 循环 · 工具 · 技能 · 委派 · 会话 · 记忆        登录/注册/刷新 · 用户 · 配额 · 插件 · 权限
          │                                                    │
          ▼                                                    ▼
   LLM（Qwen / 智谱 / OpenAI / Anthropic / Mock）     PostgreSQL（业务库）
   PostgreSQL + pgvector（会话、记忆）
```

| 包                                           | 职责                                                                                                                     |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| [`agentcook-core`](agentcook-core)           | Agent 引擎：流式 ReAct 循环、并行工具执行与超时、策略钩子、上下文窗口、子 Agent 委派、`@tool` 装饰器、System Prompt 构建 |
| [`agentcook-providers`](agentcook-providers) | 模型适配：OpenAI 兼容（Qwen / 智谱 / OpenAI）、Anthropic（工具调用 + 提示缓存）、降级链、离线 Mock 模型                  |
| [`agentcook-storage`](agentcook-storage)     | 存储：会话转录、Agent 记忆（pgvector）、对象存储                                                                         |
| [`agentcook`](agentcook)                     | 运行时服务：聊天 SSE、运行管理（可取消、断线不丢）、会话、Agent 规格（YAML）、工具包、技能、日志流、委派记录、鉴权、指标 |
| [`agentcook-java`](agentcook-java)           | 业务后端（DDD 四层）：账号与 JWT 签发、角色、配额、插件、连接器、权限                                                    |
| [`agentcook-app`](agentcook-app)             | 用户端：流式对话、工具/委派卡片、停止生成、会话侧栏、Agent 选择                                                          |
| [`agentcook-admin`](agentcook-admin)         | 管理端：用户、插件、权限、技能目录、实时日志、仪表盘                                                                     |
| [`agentcook-swarm`](agentcook-swarm)         | 微服务部署形态：Traefik 网关 + gRPC + etcd                                                                               |
| [`agentcook-starter`](agentcook-starter)     | 教学最小集（教程第 22–25 讲）                                                                                            |
| [`deploy/helm`](deploy/helm)                 | Kubernetes Helm chart                                                                                                    |

架构细节：[ARCHITECTURE.md](ARCHITECTURE.md)；设计决策：[docs/adr/](docs/adr/)（Agent 循环与事件协议见 [ADR-020](docs/adr/ADR-020-agent-loop-and-event-protocol.md)）。

## Agent Harness 的 9 个维度

| 维度          | AgentCook 的实现                                                                                                             |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Agent 循环    | `AgentRunner`：流式、类型化事件（`run_started` / `text_delta` / `tool_call` / `tool_result` / `run_completed`…），轮数预算   |
| 工具调度      | `@tool` 从函数签名生成 JSON Schema；并行执行、单工具超时、参数校验、`ToolPolicy` 白名单/禁用                                 |
| System Prompt | 稳定段在前、动态段在后（日期精确到天），对提示缓存友好                                                                       |
| 上下文管理    | `ContextWindow` 按完整交换裁剪，不会拆开 tool_use / tool_result；中日韩文本的 token 估算                                     |
| 子 Agent      | `AgentTool` 委派：深度限制、委派记录（谁 → 谁、耗时、结果）                                                                  |
| 记忆          | 每个（Agent，用户）独立实例；事件、Soul、向量检索（pgvector）                                                                |
| 安全          | JWT（Java 签发 / Python 校验，拒绝 refresh token 当 access 用）、管理员角色、会话归属校验、`fetch_url` 防 SSRF、工具禁用名单 |
| 可观测性      | Prometheus 指标（按路由模板）、结构化日志实时流、运行追踪；OpenTelemetry 可选                                                |
| 成本          | 降级链（主模型失败才降级，且只在首个 token 之前）、免费额度与模型分层（ADR-018）                                             |

## 开发

前置：Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)、Node.js 20+ 与 pnpm 9、Java 17+（`./mvnw` 已内置）、Docker。

```bash
make help            # 全部命令
make run / web / admin
make dev             # docker-compose 中间件（Postgres、Redis、Jaeger…）+ 运行时
make test-py         # Python 全量测试（集成测试用 testcontainers，需要 Docker）
make test-java       # Java 测试
make test-contract   # Pact 契约：前端期望 vs 运行时实际返回（无需 broker）
pnpm turbo run lint test build   # 前端
pnpm e2e             # Playwright（需先 make run + make web）
```

| 服务                    | 端口         |
| ----------------------- | ------------ |
| Agent 运行时（FastAPI） | 8000         |
| 业务后端（Spring Boot） | 8080         |
| 管理端 / 用户端（Vite） | 5173 / 5174  |
| PostgreSQL（pgvector）  | 5432         |
| Redis                   | 6379         |
| Jaeger / Prometheus     | 16686 / 9090 |

## 部署

- **单机容器**：`docker build -f agentcook/Dockerfile -t agentcook-runtime .`（生产模式默认要求鉴权，需 `AGENTCOOK_JWT_SECRET`）
- **微服务**：`AGENTCOOK_JWT_SECRET=$(openssl rand -hex 32) docker compose -f agentcook-swarm/docker-compose.swarm.yml up --build`，用户端 `/app/`、管理端 `/admin/`
- **Kubernetes**：[`deploy/helm`](deploy/helm)，见 [DEPLOYMENT.md](DEPLOYMENT.md)

## 配套教程

📚 [agentcook-tutorial](https://github.com/agentcook-cc/agentcook-tutorial) —— 30 讲主线 + 附录，从机会判断、架构设计一路讲到上线运营。第 22–25 讲配套 [`agentcook-starter`](agentcook-starter)。

💬 讨论区：[github.com/agentcook-cc/agentcook/discussions](https://github.com/agentcook-cc/agentcook/discussions)

## License

MIT © 2026 agentcook contributors
