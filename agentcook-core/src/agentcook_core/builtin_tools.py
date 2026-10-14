"""Built-in tools every agent can opt into.

Small, dependency-free and safe by construction:

- :data:`current_time` — wall-clock time in any IANA timezone.
- :data:`calculator` — arithmetic via an AST whitelist (no ``eval``).
- :func:`make_load_skill_tool` — progressive skill disclosure: the
  system prompt lists skill *names*; the model pulls a skill's full body
  only when it needs it, keeping the prompt short.
"""

from __future__ import annotations

import ast
import datetime as dt
import math
import operator
from collections.abc import Callable
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agentcook_core.skill_loader import SkillRegistry
from agentcook_core.tools import FunctionTool, ToolInputError, tool


@tool
def current_time(
    timezone: Annotated[str, "IANA timezone name, e.g. 'Asia/Shanghai' or 'UTC'"] = "UTC",
) -> dict[str, str]:
    """Get the current date and time in a timezone."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ToolInputError(f"unknown timezone {timezone!r}; use an IANA name like 'UTC'") from exc
    now = dt.datetime.now(tz=zone)
    return {
        "timezone": timezone,
        "iso": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
    }


_BIN_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_FUNCS: dict[str, Callable[..., Any]] = {
    name: getattr(math, name)
    for name in (
        "sqrt",
        "log",
        "log10",
        "log2",
        "exp",
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "floor",
        "ceil",
        "fabs",
        "factorial",
        "radians",
        "degrees",
    )
}
_FUNCS.update({"abs": abs, "round": round, "min": min, "max": max})
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_MAX_EXPONENT = 1_000
_MAX_FACTORIAL = 500


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ToolInputError(f"exponent too large (max {_MAX_EXPONENT})")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        if node.keywords:
            raise ToolInputError("keyword arguments are not supported")
        args = [_eval_node(a) for a in node.args]
        if node.func.id == "factorial" and args and args[0] > _MAX_FACTORIAL:
            raise ToolInputError(f"factorial argument too large (max {_MAX_FACTORIAL})")
        return _FUNCS[node.func.id](*args)
    raise ToolInputError(f"unsupported expression element: {ast.dump(node)[:60]}")


@tool
def calculator(
    expression: Annotated[str, "Arithmetic expression, e.g. '(1299 * 0.85) - 50' or 'sqrt(2)'"],
) -> dict[str, Any]:
    """Evaluate an arithmetic expression exactly. Use this instead of doing math in your head.

    Supports + - * / // % **, parentheses, constants pi/e/tau and
    functions sqrt, log, log10, log2, exp, sin, cos, tan, floor, ceil,
    abs, round, min, max, factorial.
    """
    if len(expression) > 500:
        raise ToolInputError("expression too long (max 500 characters)")
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
    except SyntaxError as exc:
        raise ToolInputError(f"invalid expression: {exc.msg}") from exc
    try:
        value = _eval_node(tree)
    except ZeroDivisionError as exc:
        raise ToolInputError("division by zero") from exc
    except (OverflowError, ValueError) as exc:
        raise ToolInputError(f"math error: {exc}") from exc
    if isinstance(value, float):
        # Strip binary floating-point noise (0.1 + 0.2 → 0.3) — the model
        # will quote this number to the user verbatim.
        value = float(f"{value:.12g}")
        if value.is_integer() and abs(value) < 1e15:
            value = int(value)
    return {"expression": expression, "result": value}


def make_load_skill_tool(registry: SkillRegistry, *, name: str = "load_skill") -> FunctionTool:
    """Build a tool that returns a skill's full instructions on demand."""

    def load_skill(skill: Annotated[str, "Exact skill name from the Skills catalog"]) -> str:
        entry = registry.get(skill)
        if entry is None:
            available = ", ".join(sorted(e.manifest.name for e in registry.list_skills()))
            raise ToolInputError(f"unknown skill {skill!r}; available: {available or '(none)'}")
        return f"# Skill: {entry.manifest.name} (v{entry.manifest.version})\n\n{entry.load()}"

    return FunctionTool(
        load_skill,
        name=name,
        description=(
            "Load the full instructions of a skill listed in the Skills section of your "
            "system prompt. Call this before working on a task that matches a skill."
        ),
    )


BUILTIN_TOOLS = (current_time, calculator)

__all__ = ["BUILTIN_TOOLS", "calculator", "current_time", "make_load_skill_tool"]
