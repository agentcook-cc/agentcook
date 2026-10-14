# ADR-020: Agent 循环进入 agentcook-core，聊天改为类型化事件流

## Status

**Accepted**（2026-10，运行时 v2.0.0）。取代 ADR-017 中"chat 端点直接转发模型文本流"的实现方式；ADR-017 关于默认接入真实模型的决定不变。

## Context

v1 的 `/api/v1/chat/stream` 把用户消息原样转给模型，再把模型的文本增量转成 SSE。它能聊天，但不是 Agent：

- **没有工具调用**：`agentcook-core` 定义了 Tool / Skill 协议，但聊天路径从不把工具交给模型，也不执行模型请求的工具。Anthropic 适配器甚至不转换 `tool_use` / `tool_result`。
- **前端看不到过程**：协议只有 `role` / `content` / `done`，无法表达"正在调用计算器""委派给分析师"。
- **运行绑在 HTTP 连接上**：浏览器断开 = 生成中断 = 转录丢失；没有取消接口，"停止"只是前端不再读流。
- **降级不安全**：降级链在流中途失败时会换模型重来，用户看到两段拼接的回答。
- **会话、记忆按 agent 名混用**：所有用户共享同一个 `assistant` 记忆实例。

教程第 8–15 讲描述的 Agent（循环、工具、上下文、子 Agent、记忆）在代码里并不存在于聊天主路径上。

## Decision

### 1. 循环放进 agentcook-core，而不是运行时服务

`AgentRunner.run_stream()` 是唯一的循环实现：调用模型 → 收集工具调用 → 并行执行（单工具超时、参数按 JSON Schema 校验、`ToolPolicy` 过滤）→ 把结果追加进上下文 → 再调用，直到模型不再请求工具或用完轮数预算。运行时、gRPC 服务、测试都调用同一个实现。

循环产出**类型化事件**：`RunStarted`、`TextDelta`、`ToolCallStarted`、`ToolCallCompleted`、`TurnCompleted`、`RunCompleted`、`RunFailed`。钩子（`RunHooks`）分两类：策略钩子出错即失败（fail-closed），观察钩子出错只记日志（fail-open）——指标、日志不能拖垮一次对话。

子 Agent 委派用 `AgentTool` 实现：主 Agent 看到的是一个名为 `delegate_to_<agent>` 的普通工具。深度受限，每次委派记录在运行上下文里（谁、给谁、任务、耗时、成败），随 `done` 帧返回并进入委派日志。

### 2. SSE 帧协议：新增 `type`，保留 v1 字段

每一帧都是一个 JSON 对象，**始终带 v1 字段** `role`、`content`、`done`，只拼接 `content` 的旧客户端行为不变。新字段：

| `type`        | 何时         | 额外字段                                                                                            |
| ------------- | ------------ | --------------------------------------------------------------------------------------------------- |
| `start`       | 运行开始     | `run_id`、`session_id`、`metadata`（agent、model、provider、warnings）                              |
| `delta`       | 模型文本增量 | `content`                                                                                           |
| `tool_call`   | 工具开始执行 | `tool_call`：`id`、`name`、`arguments`、`status=running`、`turn`                                    |
| `tool_result` | 工具结束     | `tool_call`：再加 `status=success/error`、`output`（截断）、`error`、`duration_ms`                  |
| `done`        | 运行结束     | `run_id`、`metadata`：`usage`、`finish_reason`（`stop` / `max_turns` / `cancelled`）、`delegations` |
| `error`       | 运行失败     | `error`，`done=true`                                                                                |

前端按 `tool_call.id` 更新同一张卡片。长时间工具执行期间每 15 秒发送 `: ping` 注释行保活。

### 3. 运行独立于连接

`RunManager` 持有运行：HTTP 连接只是订阅者。断开连接不取消运行，结果照常持久化；`POST /api/v1/chat/runs/{run_id}/cancel` 才取消，已生成内容以 `finish_reason=cancelled` 保存。同一会话同时只允许一个运行，第二个请求得到 `409 SESSION_BUSY`。

### 4. 降级只发生在首个 token 之前

`FallbackProvider` 在主模型产出第一个数据块之前失败时才切换到下一个；之后的失败作为运行失败上报，绝不把两个模型的回答拼在一起。

### 5. 会话与记忆按用户隔离

会话转录存于 `ConversationStore`（内存或 Postgres），带所有者；访问他人会话与访问不存在的会话返回相同的 404。记忆实例按（Agent，用户）划分。

## Consequences

**好处**

- 教程里描述的 Agent 能力全部走在真实聊天路径上，并被测试覆盖（核心循环、提供方转换、运行时路由、前端 reducer、Playwright 端到端）。
- 离线 `MockProvider` 实现相同的流式工具调用接口，无 API Key 时整条链路（工具、委派、持久化、取消）照样运行，开发、演示、CI 都不依赖外部模型。
- 前端可以如实展示 Agent 在做什么，"停止"真正释放服务端资源。

**代价**

- SSE 帧变大（工具帧带参数与输出）；输出在帧里截断，完整结果只留在转录中。
- 运行与连接解耦后，进行中的运行保存在运行时进程内，"一个会话同时一个运行"的约束也是进程内的。多副本部署需要按会话做粘性路由，否则取消请求可能落到别的副本；跨副本取消与互斥留待引入共享的运行注册表（如 Redis）。
- gRPC `ChatService` 的 `ChatFrame` 只有 v1 字段，工具帧以 `role=tool` + JSON 内容转发。

## Related

- ADR-012 Agent Harness 理念 · ADR-013 双后端 · ADR-017 chat 接真实模型 · ADR-018 配额与模型分层
- 代码：`agentcook-core/src/agentcook_core/agent.py`、`agentcook/src/agentcook_app/chat_service.py`、`agentcook/src/agentcook_app/runs.py`
- 前端：`agentcook-app/src/hooks/useAgentChat.ts`、`agentcook-app/src/lib/sse.ts`
