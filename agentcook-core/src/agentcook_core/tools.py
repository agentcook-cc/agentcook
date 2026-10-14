"""Tool authoring + registry.

Turning a Python function into something an LLM can call takes three
pieces of metadata — a name, a description, and a JSON-Schema for the
arguments. Writing that schema by hand is the #1 source of drift
between what a tool *accepts* and what the model is *told* it accepts,
so this module derives it from the function signature instead::

    from agentcook_core.tools import tool

    @tool
    async def get_weather(city: str, unit: Literal["c", "f"] = "c") -> dict:
        \"\"\"Look up the current weather for a city.

        Args:
            city: City name, e.g. "Beijing".
            unit: Temperature unit.
        \"\"\"
        ...

``get_weather`` is now a :class:`FunctionTool` satisfying
:class:`~agentcook_core.protocols.ToolProtocol`. Sync functions are run
in a worker thread so they never block the event loop.

Tools that need per-run information (user id, session id, shared
state) declare a parameter annotated with :class:`RunContext`; it is
injected at call time and hidden from the schema the model sees.

stdlib-only.
"""

from __future__ import annotations

import asyncio
import enum
import functools
import inspect
import json
import re
import types
import typing
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal, get_args, get_origin

from agentcook_core.protocols import ToolProtocol
from agentcook_core.types import ToolResult

# ---------------------------------------------------------------------------
# Run context (injected into tools that ask for it)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RunContext:
    """Per-run information shared between the runner and tools.

    ``state`` is a scratch dict tools may read/write to coordinate within
    a single run (e.g. a delegation log). ``depth`` counts sub-agent
    nesting so recursive delegation can be bounded.
    """

    run_id: str
    agent_name: str
    session_id: str | None = None
    user_id: str | None = None
    depth: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


_current_run_context: ContextVar[RunContext | None] = ContextVar(
    "agentcook_run_context", default=None
)


def current_run_context() -> RunContext | None:
    """Return the :class:`RunContext` of the agent run executing this tool."""
    return _current_run_context.get()


def _set_run_context(ctx: RunContext | None) -> Any:
    return _current_run_context.set(ctx)


def _reset_run_context(token: Any) -> None:
    _current_run_context.reset(token)


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------

_PRIMITIVES: dict[Any, dict[str, Any]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    dict: {"type": "object"},
    list: {"type": "array"},
    tuple: {"type": "array"},
    type(None): {"type": "null"},
}


def _json_schema_for(annotation: Any) -> dict[str, Any]:
    """Map a Python type annotation onto a JSON-Schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is typing.Annotated:
        base, *extras = args
        schema = dict(_json_schema_for(base))
        desc = next((e for e in extras if isinstance(e, str)), None)
        if desc:
            schema["description"] = desc
        return schema

    if origin in (typing.Union, types.UnionType):
        non_null = [a for a in args if a is not type(None)]
        if len(non_null) == 1:
            return _json_schema_for(non_null[0])
        return {"anyOf": [_json_schema_for(a) for a in non_null]}

    if origin is Literal:
        values = list(args)
        schema: dict[str, Any] = {"enum": values}
        kinds = {type(v) for v in values}
        if len(kinds) == 1 and next(iter(kinds)) in _PRIMITIVES:
            schema.update(_PRIMITIVES[next(iter(kinds))])
        return schema

    if origin in (list, tuple, set, frozenset, Sequence, Iterable):
        item = args[0] if args else Any
        schema = {"type": "array"}
        item_schema = _json_schema_for(item)
        if item_schema:
            schema["items"] = item_schema
        return schema

    if origin is dict:
        schema = {"type": "object"}
        if len(args) == 2:
            value_schema = _json_schema_for(args[1])
            if value_schema:
                schema["additionalProperties"] = value_schema
        return schema

    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        values = [m.value for m in annotation]
        schema = {"enum": values}
        kinds = {type(v) for v in values}
        if len(kinds) == 1 and next(iter(kinds)) in _PRIMITIVES:
            schema.update(_PRIMITIVES[next(iter(kinds))])
        return schema

    if annotation in _PRIMITIVES:
        return dict(_PRIMITIVES[annotation])

    return {}


_ARGS_HEADER = re.compile(r"^\s*(Args|Arguments|Parameters)\s*:\s*$", re.IGNORECASE)
_SECTION_HEADER = re.compile(r"^\s*[A-Z][A-Za-z ]*:\s*$")
_ARG_LINE = re.compile(r"^\s*(\*{0,2}\w+)\s*(\([^)]*\))?\s*:\s*(.*)$")


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """Split a Google-style docstring into ``(summary, {param: description})``.

    The summary is everything before the first section header; parameter
    descriptions come from the ``Args:`` section (continuation lines are
    joined).
    """
    if not doc:
        return "", {}
    lines = inspect.cleandoc(doc).splitlines()
    summary_lines: list[str] = []
    params: dict[str, str] = {}
    i = 0
    while i < len(lines) and not _SECTION_HEADER.match(lines[i]):
        summary_lines.append(lines[i])
        i += 1
    current: str | None = None
    in_args = False
    for line in lines[i:]:
        if _ARGS_HEADER.match(line):
            in_args = True
            current = None
            continue
        if _SECTION_HEADER.match(line):
            in_args = False
            current = None
            continue
        if not in_args:
            continue
        m = _ARG_LINE.match(line)
        if m and (len(line) - len(line.lstrip())) <= 4:
            current = m.group(1).lstrip("*")
            params[current] = m.group(3).strip()
        elif current and line.strip():
            params[current] = f"{params[current]} {line.strip()}".strip()
    summary = "\n".join(summary_lines).strip()
    return summary, params


def _is_context_param(annotation: Any) -> bool:
    if annotation is RunContext:
        return True
    if isinstance(annotation, str):
        return annotation in ("RunContext", "RunContext | None", "Optional[RunContext]")
    origin = get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return any(a is RunContext for a in get_args(annotation))
    return False


def schema_from_function(fn: Callable[..., Any]) -> tuple[dict[str, Any], str | None]:
    """Build an object JSON-Schema from *fn*'s signature.

    Returns ``(schema, context_param_name)`` — the latter names the
    parameter that receives the :class:`RunContext` (if any).
    """
    sig = inspect.signature(fn)
    try:
        hints = typing.get_type_hints(fn, include_extras=True)
    except Exception:  # forward refs we can't resolve — fall back to raw
        hints = {}
    _, param_docs = parse_docstring(fn.__doc__)

    properties: dict[str, Any] = {}
    required: list[str] = []
    context_param: str | None = None

    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        annotation = hints.get(name, param.annotation)
        if _is_context_param(annotation):
            context_param = name
            continue
        prop = _json_schema_for(annotation)
        if name in param_docs and "description" not in prop:
            prop["description"] = param_docs[name]
        if param.default is not inspect.Parameter.empty:
            default = param.default
            if isinstance(default, enum.Enum):
                default = default.value
            if default is None or isinstance(default, (str, int, float, bool, list, dict)):
                prop["default"] = default
        else:
            required.append(name)
        properties[name] = prop

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    schema["additionalProperties"] = False
    return schema, context_param


# ---------------------------------------------------------------------------
# Argument validation (minimal — catches the mistakes models actually make)
# ---------------------------------------------------------------------------

_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, (list, tuple)),
    "null": lambda v: v is None,
}


def validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> str | None:
    """Return an error message if *arguments* violate *schema*, else ``None``.

    Checks required keys, unknown keys (when ``additionalProperties`` is
    false), primitive types and enums at the top level. Deliberately not
    a full JSON-Schema validator — the goal is a precise, model-readable
    error the LLM can self-correct from.
    """
    if not isinstance(arguments, dict):
        return "arguments must be a JSON object"
    props: dict[str, Any] = schema.get("properties") or {}
    missing = [k for k in schema.get("required", ()) if k not in arguments]
    if missing:
        return f"missing required argument(s): {', '.join(missing)}"
    if schema.get("additionalProperties") is False:
        unknown = [k for k in arguments if k not in props]
        if unknown:
            allowed = ", ".join(props) or "(none)"
            return f"unknown argument(s): {', '.join(unknown)}; allowed: {allowed}"
    for key, value in arguments.items():
        prop = props.get(key)
        if not prop:
            continue
        expected = prop.get("type")
        if isinstance(expected, str) and expected in _TYPE_CHECKS:
            if value is None and prop.get("default", ...) is None:
                continue
            if not _TYPE_CHECKS[expected](value):
                return f"argument {key!r} must be of type {expected}, got {type(value).__name__}"
        if "enum" in prop and value not in prop["enum"]:
            return f"argument {key!r} must be one of {prop['enum']!r}, got {value!r}"
    return None


# ---------------------------------------------------------------------------
# FunctionTool
# ---------------------------------------------------------------------------


class ToolInputError(ValueError):
    """Raise from a tool body to report a caller (model) mistake.

    The message is returned to the model verbatim so it can retry with
    corrected arguments.
    """


class FunctionTool:
    """Wrap a sync or async callable as a :class:`ToolProtocol`."""

    def __init__(
        self,
        fn: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        parameters_schema: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> None:
        summary, _ = parse_docstring(fn.__doc__)
        self._fn = fn
        self._name = name or fn.__name__
        self._description = (description or summary or self._name).strip()
        generated, context_param = schema_from_function(fn)
        self._schema = parameters_schema or generated
        self._context_param = context_param
        self._is_async = inspect.iscoroutinefunction(fn)
        self.timeout = timeout
        functools.update_wrapper(self, fn)  # type: ignore[arg-type]

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return self._schema

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the wrapped function directly (handy in unit tests)."""
        return self._fn(*args, **kwargs)

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        error = validate_arguments(self._schema, arguments)
        if error:
            return ToolResult(success=False, error=error, metadata={"kind": "invalid_arguments"})
        kwargs = dict(arguments)
        if self._context_param:
            kwargs[self._context_param] = current_run_context()
        try:
            if self._is_async:
                output = await self._fn(**kwargs)
            else:
                output = await asyncio.to_thread(functools.partial(self._fn, **kwargs))
        except ToolInputError as exc:
            return ToolResult(success=False, error=str(exc), metadata={"kind": "invalid_input"})
        except Exception as exc:  # tools must not raise per ToolProtocol
            return ToolResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                metadata={"kind": "exception"},
            )
        if isinstance(output, ToolResult):
            return output
        return ToolResult(success=True, output=output)

    def __repr__(self) -> str:
        return f"FunctionTool(name={self._name!r})"


def tool(
    fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    timeout: float | None = None,
) -> Any:
    """Decorator turning a function into a :class:`FunctionTool`.

    Usable bare (``@tool``) or with options (``@tool(name="search")``).
    """

    def wrap(f: Callable[..., Any]) -> FunctionTool:
        return FunctionTool(f, name=name, description=description, timeout=timeout)

    if fn is not None:
        return wrap(fn)
    return wrap


# ---------------------------------------------------------------------------
# Toolset — a named collection
# ---------------------------------------------------------------------------

_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class DuplicateToolError(ValueError):
    """Two tools in one :class:`Toolset` share a name."""


class Toolset:
    """Ordered name → tool mapping handed to an agent.

    Names must match ``^[a-zA-Z0-9_-]{1,64}$`` — the intersection of
    what OpenAI and Anthropic accept — so a toolset that validates here
    is portable across providers.
    """

    def __init__(self, tools: Iterable[ToolProtocol] = ()) -> None:
        self._tools: dict[str, ToolProtocol] = {}
        for t in tools:
            self.add(t)

    def add(self, t: ToolProtocol, *, replace: bool = False) -> ToolProtocol:
        if not isinstance(t, ToolProtocol):
            raise TypeError(f"{t!r} does not satisfy ToolProtocol")
        if not _TOOL_NAME_RE.match(t.name):
            raise ValueError(f"Invalid tool name {t.name!r}: must match ^[a-zA-Z0-9_-]{{1,64}}$")
        if t.name in self._tools and not replace:
            raise DuplicateToolError(f"Tool {t.name!r} already registered")
        self._tools[t.name] = t
        return t

    def register(self, fn: Callable[..., Any]) -> FunctionTool:
        """Decorator: ``@toolset.register`` wraps + adds a function."""
        ft = fn if isinstance(fn, FunctionTool) else FunctionTool(fn)
        self.add(ft)
        return ft

    def get(self, name: str) -> ToolProtocol | None:
        return self._tools.get(name)

    def remove(self, name: str) -> bool:
        return self._tools.pop(name, None) is not None

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def merged(self, other: Iterable[ToolProtocol]) -> Toolset:
        """Return a new toolset with *other* layered on top (later wins)."""
        out = Toolset(self)
        for t in other:
            out.add(t, replace=True)
        return out

    def subset(self, names: Iterable[str]) -> Toolset:
        """Return a toolset restricted to *names* (unknown names ignored)."""
        wanted = set(names)
        return Toolset(t for n, t in self._tools.items() if n in wanted)

    def describe(self) -> list[dict[str, Any]]:
        """Plain-dict view for APIs / admin UIs."""
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters_schema}
            for t in self._tools.values()
        ]

    def __iter__(self) -> Iterator[ToolProtocol]:
        return iter(list(self._tools.values()))

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"Toolset({self.names!r})"


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def render_tool_output(result: ToolResult, *, max_chars: int = 8_000) -> str:
    """Serialize a :class:`ToolResult` into the text the model will read.

    Errors are prefixed with ``ERROR:`` so models reliably notice them;
    structured outputs are JSON-encoded; oversize outputs are truncated
    with an explicit marker (silent truncation makes models hallucinate
    the missing tail).
    """
    if not result.success:
        text = f"ERROR: {result.error or 'tool failed'}"
    elif result.output is None:
        text = "(no output)"
    elif isinstance(result.output, str):
        text = result.output
    else:
        try:
            text = json.dumps(result.output, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(result.output)
    if max_chars > 0 and len(text) > max_chars:
        omitted = len(text) - max_chars
        text = f"{text[:max_chars]}\n…[truncated {omitted} characters]"
    return text


__all__ = [
    "DuplicateToolError",
    "FunctionTool",
    "RunContext",
    "ToolInputError",
    "Toolset",
    "current_run_context",
    "parse_docstring",
    "render_tool_output",
    "schema_from_function",
    "tool",
    "validate_arguments",
]
