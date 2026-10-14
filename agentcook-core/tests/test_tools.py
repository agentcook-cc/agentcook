"""Tests for agentcook_core.tools — schema generation, invocation, Toolset."""

from __future__ import annotations

import asyncio
import enum
from typing import Annotated, Literal

import pytest
from agentcook_core import ToolProtocol, ToolResult
from agentcook_core.tools import (
    DuplicateToolError,
    FunctionTool,
    RunContext,
    ToolInputError,
    Toolset,
    _reset_run_context,
    _set_run_context,
    parse_docstring,
    render_tool_output,
    schema_from_function,
    tool,
    validate_arguments,
)

pytestmark = pytest.mark.unit


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


def test_schema_from_signature_maps_types_defaults_and_docs() -> None:
    def search(
        query: str,
        limit: int = 5,
        ratio: float | None = None,
        tags: list[str] | None = None,
        mode: Literal["fast", "deep"] = "fast",
        color: Color = Color.RED,
        note: Annotated[str, "free text note"] = "",
    ) -> list[str]:
        """Search the catalog.

        Args:
            query: What to look for.
            limit: Max results
                to return.
        """
        return []

    schema, ctx_param = schema_from_function(search)
    assert ctx_param is None
    props = schema["properties"]
    assert schema["required"] == ["query"]
    assert schema["additionalProperties"] is False
    assert props["query"] == {"type": "string", "description": "What to look for."}
    assert props["limit"] == {
        "type": "integer",
        "description": "Max results to return.",
        "default": 5,
    }
    assert props["ratio"]["type"] == "number"
    assert props["tags"] == {"type": "array", "items": {"type": "string"}, "default": None}
    assert props["mode"]["enum"] == ["fast", "deep"]
    assert props["mode"]["type"] == "string"
    assert props["color"]["enum"] == ["red", "blue"]
    assert props["color"]["default"] == "red"
    assert props["note"]["description"] == "free text note"


def test_parse_docstring_summary_and_args() -> None:
    summary, params = parse_docstring(
        """Do a thing.

        Longer explanation.

        Args:
            a: first
            b (int): second

        Returns:
            stuff
        """
    )
    assert summary == "Do a thing.\n\nLonger explanation."
    assert params == {"a": "first", "b": "second"}


def test_decorator_builds_protocol_compliant_tool() -> None:
    @tool
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    assert isinstance(add, FunctionTool)
    assert isinstance(add, ToolProtocol)
    assert add.name == "add"
    assert add.description == "Add two integers."
    assert add(2, 3) == 5  # still directly callable


def test_decorator_with_options() -> None:
    @tool(name="custom_name", description="Custom description", timeout=3)
    async def fn(x: str) -> str:
        return x

    assert fn.name == "custom_name"
    assert fn.description == "Custom description"
    assert fn.timeout == 3


async def test_invoke_sync_and_async_functions() -> None:
    @tool
    def sync_fn(x: int) -> int:
        return x * 2

    @tool
    async def async_fn(x: int) -> int:
        await asyncio.sleep(0)
        return x * 3

    assert (await sync_fn.invoke({"x": 2})) == ToolResult(success=True, output=4)
    assert (await async_fn.invoke({"x": 2})) == ToolResult(success=True, output=6)


async def test_invoke_validates_arguments() -> None:
    @tool
    def fn(x: int, mode: Literal["a", "b"] = "a") -> int:
        return x

    missing = await fn.invoke({})
    assert not missing.success and "missing required" in (missing.error or "")
    wrong_type = await fn.invoke({"x": "nope"})
    assert not wrong_type.success and "integer" in (wrong_type.error or "")
    unknown = await fn.invoke({"x": 1, "zzz": 2})
    assert not unknown.success and "unknown argument" in (unknown.error or "")
    bad_enum = await fn.invoke({"x": 1, "mode": "c"})
    assert not bad_enum.success and "one of" in (bad_enum.error or "")


async def test_invoke_turns_exceptions_into_error_results() -> None:
    @tool
    def boom() -> None:
        raise RuntimeError("kaput")

    @tool
    def bad_input() -> None:
        raise ToolInputError("try a smaller number")

    r1 = await boom.invoke({})
    assert not r1.success and r1.error == "RuntimeError: kaput"
    assert r1.metadata["kind"] == "exception"
    r2 = await bad_input.invoke({})
    assert r2.error == "try a smaller number"
    assert r2.metadata["kind"] == "invalid_input"


async def test_tool_result_passthrough() -> None:
    @tool
    def custom() -> ToolResult:
        return ToolResult(success=False, error="custom", metadata={"k": 1})

    assert await custom.invoke({}) == ToolResult(success=False, error="custom", metadata={"k": 1})


async def test_run_context_is_injected_and_hidden_from_schema() -> None:
    seen: list[RunContext | None] = []

    @tool
    def who_am_i(ctx: RunContext, greeting: str = "hi") -> str:
        seen.append(ctx)
        return f"{greeting} {ctx.user_id}"

    assert "ctx" not in who_am_i.parameters_schema["properties"]
    run_ctx = RunContext(run_id="r1", agent_name="a", user_id="u42")
    token = _set_run_context(run_ctx)
    try:
        result = await who_am_i.invoke({})
    finally:
        _reset_run_context(token)
    assert result.output == "hi u42"
    assert seen == [run_ctx]


def test_validate_arguments_allows_explicit_null_for_optional() -> None:
    schema, _ = schema_from_function(lambda x=None: x)
    assert validate_arguments(schema, {"x": None}) is None


def test_toolset_registration_and_queries() -> None:
    ts = Toolset()

    @ts.register
    def alpha() -> str:
        """A."""
        return "a"

    @tool
    def beta() -> str:
        """B."""
        return "b"

    ts.add(beta)
    assert ts.names == ["alpha", "beta"]
    assert "alpha" in ts and len(ts) == 2
    assert ts.get("beta") is beta
    with pytest.raises(DuplicateToolError):
        ts.add(beta)
    assert ts.subset(["beta", "missing"]).names == ["beta"]
    assert [d["name"] for d in ts.describe()] == ["alpha", "beta"]
    assert ts.remove("alpha") and ts.names == ["beta"]


def test_toolset_rejects_invalid_names_and_non_tools() -> None:
    ts = Toolset()
    with pytest.raises(ValueError, match="Invalid tool name"):
        ts.add(FunctionTool(lambda: None, name="has space"))
    with pytest.raises(TypeError):
        ts.add(object())  # type: ignore[arg-type]


def test_toolset_merged_later_wins() -> None:
    a1 = FunctionTool(lambda: 1, name="a", description="first")
    a2 = FunctionTool(lambda: 2, name="a", description="second")
    merged = Toolset([a1]).merged([a2])
    assert merged.get("a") is a2


def test_render_tool_output_variants() -> None:
    assert render_tool_output(ToolResult(success=True, output="hi")) == "hi"
    assert render_tool_output(ToolResult(success=True, output={"a": "中"})) == '{"a": "中"}'
    assert render_tool_output(ToolResult(success=True)) == "(no output)"
    assert render_tool_output(ToolResult(success=False, error="bad")) == "ERROR: bad"
    long = render_tool_output(ToolResult(success=True, output="x" * 50), max_chars=10)
    assert long.startswith("x" * 10) and "truncated 40 characters" in long
