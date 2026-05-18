"""Demo: declarative multi-agent routing with LangGraph.

Run:
    pip install -r requirements.txt
    python demo_multi_agent.py
"""

import os
from config_compiler import compile_router_config, AgentState

def main():
    config_path = os.path.join(os.path.dirname(__file__), "router_config.yaml")
    
    # Compile YAML → LangGraph StateGraph
    graph = compile_router_config(config_path)
    print("✅ YAML config compiled to LangGraph StateGraph")
    print()

    # Test cases
    test_tasks = [
        "帮我搜索一下 LangGraph 的最新文档",
        "写一个 Python 排序算法",
        "今天天气怎么样",
        "debug this JavaScript error",
        "research the latest AI trends",
    ]

    for task in test_tasks:
        initial_state: AgentState = {
            "messages": [],
            "current_agent": "",
            "task": task,
        }
        result = graph.invoke(initial_state)
        routed_to = result["current_agent"]
        response = result["messages"][-1]["content"] if result["messages"] else "no response"
        print(f"Task: {task}")
        print(f"  → Routed to: {routed_to}")
        print(f"  → Response: {response}")
        print()

    print("✅ Multi-agent routing demo complete!")

if __name__ == "__main__":
    main()
