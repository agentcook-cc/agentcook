"""An offline stand-in for the Anthropic client.

It implements the one call the agent makes — ``client.messages.stream(...)``
— and answers like a (very simple) model would: if the user's message
mentions a tool's keywords it calls that tool, and once the results come
back it writes an answer from them. Because it speaks the real API shape,
mock mode runs the *real* ReAct loop, tools and UI; only the model's
judgement is scripted.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass

from app.tools.registry import ToolRegistry, tool_registry


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class Message:
    content: list
    stop_reason: str
    usage: Usage
    model: str = "mock"
    role: str = "assistant"


@dataclass
class _Stream:
    message: Message
    delay: float

    async def __aenter__(self) -> "_Stream":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    @property
    async def text_stream(self):
        for block in self.message.content:
            if block.type != "text":
                continue
            for i in range(0, len(block.text), 4):
                if self.delay:
                    await asyncio.sleep(self.delay)
                yield block.text[i : i + 4]

    async def get_final_message(self) -> Message:
        return self.message


class _Messages:
    def __init__(self, registry: ToolRegistry, delay: float):
        self._registry = registry
        self._delay = delay

    def stream(self, *, messages: list[dict], tools: list[dict] | None = None, **_: object) -> _Stream:
        content = self._respond(messages, tools or [])
        prompt_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        out_chars = sum(len(b.text) if b.type == "text" else 40 for b in content)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return _Stream(Message(content, stop, Usage(prompt_chars // 2, out_chars // 2)), self._delay)

    def _respond(self, messages: list[dict], tools: list[dict]) -> list:
        last = messages[-1]
        if (
            isinstance(last["content"], list)
            and last["content"][:1]
            and last["content"][0].get("type") == "tool_result"
        ):
            return [TextBlock(_summarise(messages[-2]["content"], last["content"]))]

        text = _latest_user_text(messages)
        offered = {t["name"] for t in tools}
        matched = [
            tool
            for tool in self._registry.all()
            if tool.name in offered and any(k.lower() in text.lower() for k in tool.keywords)
        ][:3]
        if not matched:
            return [TextBlock(_help_text(tools))]
        names = "、".join(tool.name for tool in matched)
        return [TextBlock(f"好的，我先用 {names} 查一下。")] + [
            ToolUseBlock(f"toolu_mock_{uuid.uuid4().hex[:12]}", tool.name, tool.mock_arguments(text))
            for tool in matched
        ]


class MockLLM:
    """Drop-in for ``anthropic.AsyncAnthropic`` as far as the agent loop is concerned."""

    def __init__(self, registry: ToolRegistry = tool_registry, delay: float = 0.015):
        self.messages = _Messages(registry, delay)


def _latest_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(message["content"], str):
            return message["content"]
    return ""


def _summarise(assistant_content: list[dict], results: list[dict]) -> str:
    calls = {b["id"]: b["name"] for b in assistant_content if b.get("type") == "tool_use"}
    parts = []
    for result in results:
        name = calls.get(result["tool_use_id"], "工具")
        try:
            data = json.loads(result["content"])
        except (TypeError, ValueError):
            data = result["content"]
        if result.get("is_error"):
            message = data.get("error", data) if isinstance(data, dict) else data
            parts.append(f"**{name}** 这次没成功：{message}。我先基于已有信息回答，你也可以稍后再试。")
        else:
            parts.append(f"根据 **{name}** 的结果：\n{_render(data)}")
    parts.append("（Mock 模式：以上由模拟模型按模板整理。关闭 MOCK_MODE 并配置 API Key 后，这里会是真实模型的分析。）")
    return "\n\n".join(parts)


def _render(data: object) -> str:
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return "\n".join(f"- **{r.get('title', '')}**：{r.get('snippet', '')}" for r in data["results"])
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, list):
                value = "；".join(json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v) for v in value)
            lines.append(f"- {key}：{value}")
        return "\n".join(lines)
    return str(data)


def _help_text(tools: list[dict]) -> str:
    tool_lines = (
        "\n".join(f"- `{t['name']}`：{t['description'].split('。')[0]}" for t in tools) or "- （还没有注册工具）"
    )
    return (
        "你好！我是 WorkAgent 的演示版（Mock 模式，不调用真实模型，也不消耗额度）。\n\n"
        "可以试试这样问：\n"
        "- 搜索一下蓝牙耳机最近有什么热门新品\n"
        "- 帮我分析一下竞品A的定价策略\n"
        "- 最近7天哪个商品卖得最好？\n\n"
        f"我现在能用的工具：\n{tool_lines}"
    )
