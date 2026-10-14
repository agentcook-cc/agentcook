"""Chapter 24 exercise: a calculator — without ``eval``.

``eval`` on model- or user-supplied text is a remote-code-execution hole, and
even a strict character whitelist can't stop ``9**9**9**9`` from pinning the
CPU. Instead we parse the expression and only evaluate number nodes and
arithmetic operators, with a cap on exponents and result size.
"""

import ast
import operator
import re

from app.tools.base import BaseTool
from app.tools.registry import tool_registry

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
MAX_EXPONENT = 100
MAX_MAGNITUDE = 1e100

CHINESE_OPERATORS = {
    "乘以": "*",
    "除以": "/",
    "加上": "+",
    "减去": "-",
    "乘": "*",
    "除": "/",
    "加": "+",
    "减": "-",
    "×": "*",
    "÷": "/",
}
ARITHMETIC_RUN = re.compile(r"[\d.\s+\-*/()^%]+")


def safe_eval(expression: str) -> int | float:
    tree = ast.parse(expression.replace("^", "**"), mode="eval")

    def visit(node: ast.AST) -> int | float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
            return UNARY[type(node.op)](visit(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
                raise ValueError(f"指数太大（上限 {MAX_EXPONENT}）")
            result = OPERATORS[type(node.op)](left, right)
            if abs(result) > MAX_MAGNITUDE:
                raise ValueError("结果太大")
            return result
        raise ValueError("只支持数字和 + - * / // % ^ ( )")

    result = visit(tree)
    if isinstance(result, float):
        result = float(f"{result:.12g}")  # 0.1 + 0.2 → 0.3, not 0.30000000000000004
        if result.is_integer():
            result = int(result)
    return result


class CalculatorTool(BaseTool):
    name = "calculator"
    description = (
        "精确计算数学表达式：加减乘除、整除、取余、乘方、括号。"
        "涉及任何数值计算（价格、折扣、利润率、增长率）时都用它，不要心算。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式，如 '123 * 456'、'(299 - 50) * 0.85'"}
        },
        "required": ["expression"],
    }
    keywords = ("计算", "算一下", "等于多少", "乘以", "除以")

    def mock_arguments(self, message: str) -> dict:
        text = message
        for word, symbol in CHINESE_OPERATORS.items():
            text = text.replace(word, symbol)
        runs = [r.strip() for r in ARITHMETIC_RUN.findall(text) if re.search(r"\d\s*[-+*/^%]\s*[\d(]", r)]
        return {"expression": max(runs, key=len) if runs else message}

    async def execute(self, expression: str = "", **kwargs) -> dict:
        if not expression.strip():
            return {"error": "请提供数学表达式"}
        if len(expression) > 200:
            return {"error": "表达式太长（上限 200 字符）"}
        try:
            return {"expression": expression, "result": safe_eval(expression)}
        except ZeroDivisionError:
            return {"error": "除数不能为 0"}
        except (SyntaxError, ValueError, TypeError, OverflowError) as exc:
            return {"error": f"无法计算：{exc}"}


tool_registry.register(CalculatorTool())
