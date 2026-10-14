"""The heart of the agent: the ReAct loop.

    user message
      → call the LLM (with the tool definitions)
      → did it ask for tools?  no  → stream the answer, done
                               yes → run them, add the results, call the LLM again

``run_agent`` yields JSON events that the router sends as SSE:

    {"type": "text", "content": "..."}                         a piece of the answer
    {"type": "tool_call", "id", "name", "input"}               a tool is about to run
    {"type": "tool_result", "id", "name", "result", "is_error", "duration_ms"}
    {"type": "done", "rounds", "stop_reason", "usage"}         the turn finished
    {"type": "error", "message"}                               the turn failed
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import anthropic

from app.agent.context import SessionStore
from app.agent.mock_llm import MockLLM
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tracing import RequestTracer
from app.config import settings
from app.tools.registry import tool_registry

logger = logging.getLogger("agentcook")

sessions = SessionStore(max_sessions=settings.max_sessions, max_messages=settings.max_context_messages)

_llm: Any = None
_model: str | None = None


class LLMConfigError(RuntimeError):
    pass


def get_llm() -> Any:
    """The model client: MockLLM in mock mode, the Anthropic SDK otherwise."""
    global _llm
    if _llm is None:
        if settings.mock_mode:
            _llm = MockLLM()
        elif not settings.anthropic_api_key:
            raise LLMConfigError("没有配置 ANTHROPIC_API_KEY：在 .env 里填上它，或者设置 MOCK_MODE=true")
        else:
            _llm = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url or None
            )
    return _llm


async def resolve_model(client: Any) -> str:
    """MODEL_NAME if set; otherwise the newest Sonnet this API key can use (via the Models API).

    Model ids get retired; asking the API keeps an unconfigured install working.
    """
    global _model
    if settings.model_name:
        return settings.model_name
    if not isinstance(client, anthropic.AsyncAnthropic):
        return "mock"  # MockLLM and test doubles don't care
    if _model is None:
        try:
            page = await client.models.list(limit=100)  # newest first
        except anthropic.APIError as exc:
            raise LLMConfigError("无法自动选择模型：请在 .env 里设置 MODEL_NAME") from exc
        ids = [model.id for model in page.data]
        _model = next((i for i in ids if "sonnet" in i), ids[0] if ids else None)
        if _model is None:
            raise LLMConfigError("这个 API Key 没有可用的模型：请在 .env 里设置 MODEL_NAME")
        logger.info("MODEL_NAME not set, using %s", _model)
    return _model


async def run_agent(message: str, session_id: str, *, user_id: str = "", llm: Any = None) -> AsyncGenerator[str, None]:
    context = sessions.get(session_id)
    if context.lock.locked():
        yield _format_event({"type": "error", "message": "这个会话正在生成回复，请等它结束再发"})
        return

    async with context.lock:
        tracer = RequestTracer(session_id, user_id)
        snapshot = context.checkpoint()
        context.add_user_message(message)
        try:
            client = llm or get_llm()
            model = await resolve_model(client)
            for _ in range(settings.max_reasoning_rounds):
                tracer.rounds += 1

                # 1. Call the LLM, streaming its text to the user as it arrives.
                async with client.messages.stream(
                    model=model,
                    max_tokens=settings.max_tokens,
                    system=SYSTEM_PROMPT,
                    messages=context.get_messages(),
                    tools=tool_registry.get_tool_definitions(),
                ) as stream:
                    async for text in stream.text_stream:
                        yield _format_event({"type": "text", "content": text})
                    response = await stream.get_final_message()
                tracer.add_usage(response.usage)

                content = [b for b in (_block_to_dict(block) for block in response.content) if b]
                tool_calls = [b for b in content if b["type"] == "tool_use"]
                context.add_assistant_message(content or [{"type": "text", "text": "（无内容）"}])

                # 2. No tool calls → the model has answered.
                if not tool_calls:
                    yield _done(tracer, response.stop_reason)
                    return

                # 3. Run the requested tools (concurrently), then loop with the results.
                for call in tool_calls:
                    yield _format_event(
                        {"type": "tool_call", "id": call["id"], "name": call["name"], "input": call["input"]}
                    )
                outcomes = await asyncio.gather(*(_execute_tool(c["name"], c["input"]) for c in tool_calls))

                tool_results = []
                for call, (ok, result, duration_ms) in zip(tool_calls, outcomes, strict=True):
                    tracer.log_tool_call(call["name"], duration_ms, ok)
                    text = _render_for_llm(result)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": call["id"], "content": text, "is_error": not ok}
                    )
                    yield _format_event(
                        {
                            "type": "tool_result",
                            "id": call["id"],
                            "name": call["name"],
                            "result": result if len(text) < settings.max_tool_result_chars else text,
                            "is_error": not ok,
                            "duration_ms": duration_ms,
                        }
                    )
                context.add_tool_results(tool_results)

            # Out of rounds: close the turn cleanly so the history stays valid.
            notice = "\n\n（这个问题需要的步骤太多，我先回答到这里。可以把问题拆小一点再问我。）"
            context.add_assistant_message([{"type": "text", "text": notice.strip()}])
            yield _format_event({"type": "text", "content": notice})
            yield _done(tracer, "max_rounds")
        except Exception as exc:
            context.rollback(snapshot)
            tracer.finish("error")
            logger.exception("agent run failed (trace_id=%s)", tracer.trace_id)
            yield _format_event({"type": "error", "message": _describe(exc)})
        except BaseException:
            # Client disconnected / server shutting down: drop the half-finished turn.
            context.rollback(snapshot)
            tracer.finish("cancelled")
            raise


async def _execute_tool(tool_name: str, tool_input: dict) -> tuple[bool, Any, int]:
    """Run one tool with a timeout. Never raises: failures become ``{"error": ...}`` for the LLM."""
    started = time.perf_counter()

    def elapsed() -> int:
        return int((time.perf_counter() - started) * 1000)

    tool = tool_registry.get(tool_name)
    if tool is None:
        return False, {"error": f"未知工具：{tool_name}"}, elapsed()
    if not isinstance(tool_input, dict):
        return False, {"error": "工具参数必须是 JSON 对象"}, elapsed()
    try:
        result = await asyncio.wait_for(tool.execute(**tool_input), timeout=settings.tool_timeout_seconds)
    except TimeoutError:
        return False, {"error": f"工具 {tool_name} 执行超时（超过 {settings.tool_timeout_seconds:g} 秒）"}, elapsed()
    except Exception as exc:
        logger.warning("tool %s failed: %r", tool_name, exc)
        return False, {"error": f"工具 {tool_name} 执行失败：{exc}"}, elapsed()
    ok = not (isinstance(result, dict) and "error" in result)
    return ok, result, elapsed()


def _render_for_llm(result: Any) -> str:
    """Tool output as the LLM sees it — truncated so one big result can't blow the context."""
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    limit = settings.max_tool_result_chars
    if len(text) > limit:
        text = f"{text[:limit]}\n...(结果已截断，共 {len(text)} 字符)"
    return text


def _block_to_dict(block: Any) -> dict | None:
    """SDK content block → the plain dict we keep in the history."""
    if block.type == "text":
        return {"type": "text", "text": block.text} if block.text else None
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return block.model_dump(exclude_none=True) if hasattr(block, "model_dump") else None


def _done(tracer: RequestTracer, stop_reason: str | None) -> str:
    tracer.finish("ok")
    return _format_event(
        {
            "type": "done",
            "rounds": tracer.rounds,
            "stop_reason": stop_reason,
            "usage": {"input_tokens": tracer.input_tokens, "output_tokens": tracer.output_tokens},
        }
    )


def _describe(exc: Exception) -> str:
    if isinstance(exc, LLMConfigError):
        return str(exc)
    if isinstance(exc, anthropic.AuthenticationError):
        return "模型 API Key 无效或已过期，请检查 ANTHROPIC_API_KEY"
    if isinstance(exc, anthropic.RateLimitError):
        return "模型服务限流了，请稍后再试"
    if isinstance(exc, anthropic.APIConnectionError):
        return "连不上模型服务，请检查网络或 ANTHROPIC_BASE_URL"
    if isinstance(exc, anthropic.APIStatusError):
        return f"模型服务返回错误（HTTP {exc.status_code}）：{exc.message}"
    return f"出错了：{type(exc).__name__}: {exc}"


def _format_event(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)
