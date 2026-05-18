# ADR-002: Multi-Agent 引擎选用 LangGraph

## Status

Accepted (2026-05-16)

## Context

Multi-Agent 协作需要复杂的状态机管理、条件分支、循环执行等能力。自研 delegation strategy 相当于重新发明轮子，开发周期长且稳定性难以保证。

LangGraph（LangChain 生态）已成为业界事实标准，被大量生产级 Agent 产品采用，具备成熟的状态图（StateGraph）、持久化检查点、流式执行等核心能力。

## Decision

`multi_agent` 模块直接基于 LangGraph 封装，不自研底层状态机引擎。

差异化价值体现在**声明式 router config**：通过 `plugin.json` 配置 router rules，编译时自动转换为 LangGraph `StateGraph` 节点与边。

示例代码片段：

```python
class MultiAgentOrchestrator:
    """基于 LangGraph 的多 Agent 编排器"""

    def __init__(self, router_config: dict):
        self.graph = self._build_state_graph(router_config)

    def _build_state_graph(self, config: dict) -> StateGraph:
        """将声明式 router config 编译为 LangGraph StateGraph"""
        workflow = StateGraph(AgentState)

        for node_name, node_def in config["nodes"].items():
            workflow.add_node(node_name, self._create_agent_node(node_def))

        for edge in config["edges"]:
            if edge.get("condition"):
                workflow.add_conditional_edges(
                    source=edge["source"],
                    path=self._route_by_condition(edge["condition"]),
                    mapping=edge["mapping"]
                )
            else:
                workflow.add_edge(edge["source"], edge["target"])

        workflow.set_entry_point(config["entry_point"])
        return workflow.compile()

    async def execute(self, input_state: dict) -> dict:
        """执行编排流程"""
        return await self.graph.ainvoke(input_state)
```

## Consequences

### Positive
- **复用成熟实现**：LangGraph 已处理并发、重试、持久化等边缘情况
- **社区生态兼容**：可直接使用 LangChain 的 Tool、Memory、Callback 生态

### Negative
- **引入外部依赖**：项目强绑定 LangGraph，需跟进其版本更新与 breaking changes
- **学习曲线**：团队成员需掌握 LangGraph 的状态图编程范式
