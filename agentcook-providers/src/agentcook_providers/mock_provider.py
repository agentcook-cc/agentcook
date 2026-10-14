"""Deterministic offline "model" that drives the real agent loop.

The old chat mock bypassed the runtime entirely (canned SSE frames), so
"mock mode" proved nothing about tools, persistence or streaming. This
provider instead *plays the model*: it reads the conversation and the
tool list exactly like a real LLM would and decides — with transparent
keyword rules — whether to call a tool or answer. Everything downstream
(agent loop, tool execution, SSE frames, transcript storage, UI tool
cards) runs for real, with zero API keys and zero cost.

Rules (first match wins, only for tools that are actually available):

- a skill named in the system prompt's Skills catalog is mentioned → ``load_skill``
- arithmetic expression / "calculate" / "计算" → ``calculator``
- time / date / "几点" / "日期" → ``current_time``
- "remember …" / "记住…" → ``remember``; "recall" / "还记得" → ``recall``
- "search" / "搜索" / "查" → any tool whose name contains ``search``
- "delegate to X" / "ask X" / "让X" → ``delegate_to_X``
- a tool's exact name appears in the message → that tool

After tool results arrive it writes an answer that quotes them.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Any

from agentcook_core import (
    ChatChunk,
    ChatResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolProtocol,
)
from agentcook_core.tokens import estimate_messages_tokens, estimate_tokens

_CJK = re.compile(r"[㐀-鿿]")
_EXPR = re.compile(r"[-+(]*\d[\d.\s]*(?:[-+*/^%×÷][\s(]*[-+]?\d[\d.\s)]*)+")
_SKILL_LINE = re.compile(r"^- `([^`]+)`:", re.MULTILINE)
_TIME_WORDS = ("time", "date", "today", "几点", "时间", "日期", "星期", "今天", "现在")
_SEARCH_WORDS = ("search", "look up", "find", "搜索", "查一下", "查询", "搜一下", "查")
_REMEMBER = re.compile(
    r"^\s*(?:please\s+)?(?:remember(?: that)?|记住|请记住)[\s:：,，]*(.+)$", re.I
)
_RECALL_WORDS = ("recall", "do you remember", "what do you know about me", "还记得", "回忆")


def _is_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def _first_string_param(tool: ToolProtocol) -> str | None:
    schema = tool.parameters_schema or {}
    props: dict[str, Any] = schema.get("properties") or {}
    for name in schema.get("required", []):
        if props.get(name, {}).get("type") in ("string", None):
            return name
    for name, prop in props.items():
        if prop.get("type") == "string":
            return name
    return None


def _summarize_tool_output(content: str, limit: int = 600) -> str:
    text = content.strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        lines = [f"- **{k}**: {v}" for k, v in list(parsed.items())[:12]]
        text = "\n".join(lines)
    elif isinstance(parsed, list):
        lines = [f"- {json.dumps(item, ensure_ascii=False)}" for item in parsed[:8]]
        text = "\n".join(lines)
    if len(text) > limit:
        text = text[:limit] + " …"
    return text


class MockProvider:
    """Rule-based offline model satisfying ``LLMProviderProtocol``.

    Args:
        model: Reported model name.
        delay: Seconds to sleep between streamed chunks (0 in tests; the
            runtime uses a small delay so the UI shows real streaming).
    """

    def __init__(self, model: str = "mock-agent", *, delay: float = 0.0) -> None:
        self._model = model
        self._delay = delay

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return 32_000

    def count_tokens(self, text: str) -> int:
        return max(1, estimate_tokens(text))

    # -- decision logic --------------------------------------------------

    def _decide(
        self, messages: Sequence[Message], tools: Sequence[ToolProtocol]
    ) -> tuple[str, tuple[ToolCall, ...]]:
        last = messages[-1] if messages else Message(role="user", content="")
        if last.role == "tool":
            return self._answer_from_tools(messages), ()

        query = last.content.strip()
        by_name = {t.name: t for t in tools}
        call = self._pick_tool(query, by_name, messages)
        if call is not None:
            return "", (call,)
        return self._plain_answer(query, by_name), ()

    def _pick_tool(
        self,
        query: str,
        tools: dict[str, ToolProtocol],
        messages: Sequence[Message],
    ) -> ToolCall | None:
        lowered = query.lower()

        def call(name: str, **arguments: Any) -> ToolCall:
            return ToolCall(id=f"call_{uuid.uuid4().hex[:12]}", name=name, arguments=arguments)

        if "load_skill" in tools:
            system = "\n".join(m.content for m in messages if m.role == "system")
            for skill in _SKILL_LINE.findall(system):
                variants = {skill.lower(), skill.lower().replace("-", " ")}
                if any(v in lowered for v in variants):
                    return call("load_skill", skill=skill)

        if "calculator" in tools:
            match = _EXPR.search(query)
            if match and any(op in match.group(0) for op in "+-*/^%×÷"):
                expr = match.group(0).strip().replace("×", "*").replace("÷", "/")
                return call("calculator", expression=expr)

        if "remember" in tools:
            m = _REMEMBER.match(query)
            if m:
                return call("remember", content=m.group(1).strip())

        if "recall" in tools and any(w in lowered for w in _RECALL_WORDS):
            return call("recall", query=query)

        if "current_time" in tools and any(w in lowered for w in _TIME_WORDS):
            return call("current_time", timezone="Asia/Shanghai" if _is_cjk(query) else "UTC")

        for name, tool in tools.items():
            if name.startswith("delegate_to_"):
                target = name.removeprefix("delegate_to_").lower()
                target_words = {target, target.replace("_", " "), target.replace("-", " ")}
                if any(w in lowered for w in target_words) and any(
                    k in lowered for k in ("delegate", "ask", "让", "请", "交给")
                ):
                    return call(name, task=query)

        if any(w in lowered for w in _SEARCH_WORDS):
            for name, tool in tools.items():
                if "search" in name:
                    param = _first_string_param(tool)
                    if param:
                        return call(name, **{param: query})

        for name, tool in tools.items():
            if name.lower() in lowered and name not in ("load_skill",):
                param = _first_string_param(tool)
                return call(name, **({param: query} if param else {}))
        return None

    def _answer_from_tools(self, messages: Sequence[Message]) -> str:
        results: list[Message] = []
        for msg in reversed(messages):
            if msg.role != "tool":
                break
            results.append(msg)
        results.reverse()
        question = next((m.content for m in reversed(messages) if m.role == "user"), "")
        zh = _is_cjk(question)
        parts: list[str] = []
        for msg in results:
            name = msg.name or "tool"
            if msg.content.startswith("ERROR:"):
                detail = msg.content.removeprefix("ERROR:").strip()
                parts.append(
                    f"工具 `{name}` 返回了错误：{detail}"
                    if zh
                    else f"The `{name}` tool reported an error: {detail}"
                )
            elif name == "load_skill":
                heading = msg.content.splitlines()[0] if msg.content else "the skill"
                parts.append(
                    f"我已加载 {heading.removeprefix('# ')}，会按照其中的步骤处理你的请求。"
                    if zh
                    else f"I loaded {heading.removeprefix('# ')} and will follow its steps."
                )
            else:
                summary = _summarize_tool_output(msg.content)
                parts.append(
                    f"`{name}` 的结果：\n\n{summary}"
                    if zh
                    else f"Result from `{name}`:\n\n{summary}"
                )
        footer = (
            "\n\n> 这是离线 Mock 模型的回答。设置 `AGENTCOOK_LLM_PROVIDER` 即可切换到真实模型。"
            if zh
            else "\n\n> Answer composed by the offline mock model. "
            "Set `AGENTCOOK_LLM_PROVIDER` to use a real LLM."
        )
        return "\n\n".join(parts) + footer

    def _plain_answer(self, query: str, tools: dict[str, ToolProtocol]) -> str:
        zh = _is_cjk(query)
        names = [n for n in tools if n != "load_skill"]
        if zh:
            text = f"收到你的消息：「{query[:200]}」。\n\n"
            text += (
                "我目前运行在 **离线 Mock 模式**：不会调用真实大模型，"
                "但完整走通 Agent 循环、工具调用、流式输出和会话存储。"
            )
            if names:
                text += "\n\n可以试试这些能调用工具的问题：\n"
                if "calculator" in tools:
                    text += "- 计算 1299 * 0.85 - 50\n"
                if "current_time" in tools:
                    text += "- 现在几点？\n"
                if "remember" in tools:
                    text += "- 记住：我喜欢简洁的回答\n"
                text += f"\n可用工具：{', '.join(f'`{n}`' for n in names)}"
            return text
        text = f'You said: "{query[:200]}".\n\n'
        text += (
            "I'm running in **offline mock mode** — no real LLM is called, but the full agent "
            "loop, tool calls, streaming and session storage are exercised for real."
        )
        if names:
            text += "\n\nTry a question that needs a tool:\n"
            if "calculator" in tools:
                text += "- calculate 1299 * 0.85 - 50\n"
            if "current_time" in tools:
                text += "- what time is it?\n"
            if "remember" in tools:
                text += "- remember that I prefer short answers\n"
            text += f"\nAvailable tools: {', '.join(f'`{n}`' for n in names)}"
        return text

    # -- protocol --------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        text, calls = self._decide(messages, tools or ())
        return ChatResponse(
            message=Message(role="assistant", content=text, tool_calls=calls or None),
            usage=TokenUsage(
                input=estimate_messages_tokens(messages), output=estimate_tokens(text)
            ),
            finish_reason="tool_calls" if calls else "stop",
        )

    async def stream_chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        text, calls = self._decide(messages, tools or ())
        for piece in re.findall(r"\S+\s*|\s+", text):
            if self._delay:
                await asyncio.sleep(self._delay)
            yield ChatChunk(delta_content=piece)
        usage = TokenUsage(input=estimate_messages_tokens(messages), output=estimate_tokens(text))
        yield ChatChunk(
            delta_tool_calls=calls,
            finish_reason="tool_calls" if calls else "stop",
            usage=usage,
        )


__all__ = ["MockProvider"]
