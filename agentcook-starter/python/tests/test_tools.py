import asyncio

import pytest

from app.tools.base import BaseTool
from app.tools.data_query import DataQueryTool
from app.tools.mock_search import MockSearchTool
from app.tools.registry import ToolRegistry, tool_registry


def run(coro):
    return asyncio.run(coro)


class Minimal(BaseTool):
    name = "minimal"
    description = "A tool."
    parameters = {
        "type": "object",
        "properties": {"q": {"type": "string"}, "n": {"type": "integer"}, "opt": {"type": "string"}},
        "required": ["q", "n"],
    }

    async def execute(self, **kwargs):
        return kwargs


def test_definition_matches_the_anthropic_tools_format():
    assert Minimal().to_definition() == {
        "name": "minimal",
        "description": "A tool.",
        "input_schema": Minimal.parameters,
    }


def test_default_mock_arguments_fill_required_string_fields():
    assert Minimal().mock_arguments("hello") == {"q": "hello"}


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    registry.register(Minimal())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Minimal())
    assert registry.get("minimal") is not None and registry.get("nope") is None
    assert [d["name"] for d in registry.get_tool_definitions()] == ["minimal"]


def test_app_registers_the_builtin_tools():
    import app.main  # noqa: F401

    assert {"web_search", "data_query"} <= {t.name for t in tool_registry.all()}


@pytest.mark.parametrize(
    ("query", "expected"),
    [("蓝牙耳机 新品", "降噪"), ("竞品A 定价", "竞品A"), ("跨境电商", "趋势")],
)
def test_mock_search_has_three_presets(query, expected):
    result = run(MockSearchTool().execute(query=query))
    assert result["source"] == "mock"
    assert expected in result["results"][0]["title"] + result["results"][0]["snippet"]


def test_mock_search_rejects_empty_query():
    assert "error" in run(MockSearchTool().execute(query="  "))


def test_data_query_metrics():
    tool = DataQueryTool()
    revenue = run(tool.execute(metric="total_revenue", days=7))
    orders = run(tool.execute(metric="order_count", days=7, category="耳机"))
    top = run(tool.execute(metric="top_products", days=30))
    assert revenue["value"] > 0 and revenue["days"] == 7
    assert orders["category"] == "耳机" and orders["value"] > 0
    assert len(top["products"]) == 4
    assert top["products"][0]["qty"] >= top["products"][-1]["qty"]
    assert "error" in run(tool.execute(metric="total_revenue", days=90))
    assert "error" in run(tool.execute(metric="drop_table"))


def test_data_query_mock_arguments():
    tool = DataQueryTool()
    assert tool.mock_arguments("最近7天哪个商品卖得最好？") == {"metric": "top_products", "days": 7}
    assert tool.mock_arguments("昨天耳机的订单有多少") == {"metric": "order_count", "days": 1, "category": "耳机"}
