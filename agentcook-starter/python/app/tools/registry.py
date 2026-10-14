"""ToolRegistry — the one place the agent looks tools up."""

from app.tools.base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tool_definitions(self) -> list[dict]:
        """What goes into the LLM call's ``tools`` parameter."""
        return [tool.to_definition() for tool in self._tools.values()]


tool_registry = ToolRegistry()  # process-wide singleton; tool modules register into it on import
