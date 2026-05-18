## 声明式 Multi-Agent 设计

### 核心理念

agentcook 不重新发明 multi-agent 引擎，而是在 LangGraph 之上增加声明式配置层。通过 YAML/JSON 配置文件定义路由规则和 Agent 行为，运行时编译为 LangGraph StateGraph，实现"配置即代码"的开发体验。

### 与 LangGraph 原生的差异化

| 维度 | LangGraph 原生 | agentcook |
|---|---|---|
| 定义方式 | Python 代码 | YAML/JSON 声明式 |
| 上手门槛 | 需理解 StateGraph API | 填配置即可 |
| 灵活性 | 极高 | 中等（覆盖 80% 场景） |
| Plugin 集成 | 无 | Plugin Bundle 内嵌 router rules |

### 编译流程

```
YAML → load_config() → AgentConfig[] → compile_router_config() → StateGraph
```

1. **load_config()**: 解析 YAML 文件，提取 agents 列表和 routing_strategy
2. **AgentConfig[]**: 将每个 agent 的配置转换为结构化对象
3. **compile_router_config()**: 
   - 为每个 agent 创建节点函数
   - 创建 router 节点（基于 trigger_patterns 做关键词匹配或 LLM 分类）
   - 构建 StateGraph：START → router → 各 agent 节点 → END
4. **StateGraph.compile()**: 返回可执行的 LangGraph 实例

### 路由策略

- **pattern_match**：基于关键词正则匹配（POC 已实现）
  - 优点：快速、确定性高
  - 缺点：无法处理复杂意图
- **llm_classify**：调用 LLM 做意图分类（Phase 2 实现）
  - 优点：语义理解能力强
  - 缺点：延迟高、成本高

### 流式输出

基于 LangGraph 原生 stream 支持，agentcook 不额外封装。用户可直接使用 `graph.stream()` 获取流式响应。

### 生产化路径

- **Phase 2**：真实 LLM 调用 + 流式输出
  - 替换 echo 模式为真实 LLM API 调用
  - 支持 OpenAI、通义千问等多模型后端
- **Phase 3**：Plugin Bundle 内嵌 router config
  - 在 Plugin 元数据中声明 router_rules
  - 动态加载 Plugin 时自动注册到 router
- **Phase 4**：admin UI 可视化编排
  - 拖拽式 Agent 编排界面
  - 实时预览路由效果
