"""The chapter reference answers in solutions/ must keep working."""

import asyncio
import importlib
import sys

import httpx
import pytest

from app.agent import core
from app.config import settings
from app.tools.registry import tool_registry
from tests.conftest import collect


def run(coro):
    return asyncio.run(coro)


def load_tool(module: str, name: str):
    """Import a solution module and return its tool (conftest restores the registry afterwards)."""
    tool_registry.unregister(name)
    mod = importlib.reload(sys.modules[module]) if module in sys.modules else importlib.import_module(module)
    return mod, tool_registry.get(name)


def test_ch23_mock_weather():
    _, tool = load_tool("solutions.ch23.weather", "weather_query")
    assert run(tool.execute(city="上海"))["weather"] == "多云"
    assert run(tool.execute(city="拉萨"))["temp"] == "25°C"
    assert "error" in run(tool.execute(city=""))
    assert tool.mock_arguments("深圳今天天气怎么样") == {"city": "深圳"}


def test_ch23_weather_works_end_to_end_in_mock_mode():
    load_tool("solutions.ch23.weather", "weather_query")
    events = collect(core.run_agent("北京今天天气怎么样？", "w1"))
    result = next(e for e in events if e["type"] == "tool_result")
    assert result["name"] == "weather_query" and result["result"]["temp"] == "28°C"


class TestCh24Weather:
    def test_uses_mock_data_until_configured(self):
        _, tool = load_tool("solutions.ch24.weather", "weather_query")
        assert run(tool.execute(city="北京"))["source"] == "mock"

    def test_real_api(self, monkeypatch):
        _, tool = load_tool("solutions.ch24.weather", "weather_query")
        monkeypatch.setattr(settings, "mock_mode", False)
        monkeypatch.setattr(settings, "qweather_api_key", "secret-key")
        monkeypatch.setattr(settings, "qweather_api_host", "api.example.com")
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            assert request.headers["X-QW-Api-Key"] == "secret-key"
            if request.url.path == "/geo/v2/city/lookup":
                return httpx.Response(200, json={"code": "200", "location": [{"id": "101010100", "name": "北京"}]})
            now = {"temp": "21", "text": "晴", "humidity": "30", "windDir": "北风", "windScale": "2", "obsTime": "t"}
            return httpx.Response(200, json={"code": "200", "now": now})

        tool.transport = httpx.MockTransport(handler)
        result = run(tool.execute(city="北京"))
        assert result == {
            "city": "北京",
            "temp": "21°C",
            "weather": "晴",
            "humidity": "30%",
            "wind": "北风2级",
            "observed_at": "t",
            "source": "qweather",
        }
        assert all("secret-key" not in str(r.url) for r in seen)  # the key travels in a header, not the URL

    def test_service_down_is_reported_not_faked(self, monkeypatch):
        _, tool = load_tool("solutions.ch24.weather", "weather_query")
        monkeypatch.setattr(settings, "mock_mode", False)
        monkeypatch.setattr(settings, "qweather_api_key", "k")
        monkeypatch.setattr(settings, "qweather_api_host", "api.example.com")

        def handler(request):
            raise httpx.ConnectError("down")

        tool.transport = httpx.MockTransport(handler)
        assert run(tool.execute(city="北京")) == {"error": "天气服务暂时不可用，请稍后再试"}


class TestCh24Sales:
    def test_queries_a_seeded_database(self, tmp_path, monkeypatch):
        from solutions.ch24.seed_sales_db import seed

        db = seed(tmp_path / "sales.db")
        monkeypatch.setattr(settings, "sales_db_path", str(db))
        _, tool = load_tool("solutions.ch24.sales_query", "sales_query")

        revenue = run(tool.execute(metric="total_revenue", days=7))
        assert revenue["value"].startswith("¥") and revenue["value"] != "¥0.00"
        count_all = run(tool.execute(metric="order_count", days=30))["value"]
        count_phones = run(tool.execute(metric="order_count", days=30, category="手机"))["value"]
        assert 0 < count_phones < count_all
        top = run(tool.execute(metric="top_products", days=30))["products"]
        assert 1 <= len(top) <= 5 and top[0]["qty"] >= top[-1]["qty"]

    def test_guards(self, tmp_path, monkeypatch):
        _, tool = load_tool("solutions.ch24.sales_query", "sales_query")
        monkeypatch.setattr(settings, "sales_db_path", str(tmp_path / "missing.db"))
        assert "seed_sales_db" in run(tool.execute(metric="total_revenue"))["error"]
        assert "error" in run(tool.execute(metric="total_revenue", days=31))
        assert "error" in run(tool.execute(metric="1; DROP TABLE orders"))


class TestCh24Competitor:
    def test_validation_and_mock(self):
        _, tool = load_tool("solutions.ch24.competitor", "competitor_analysis")
        assert "error" in run(tool.execute())
        assert "error" in run(tool.execute(asin="nope"))
        assert "error" in run(tool.execute(product_url="file:///etc/passwd"))
        assert run(tool.execute(asin="B08XYZ1234"))["source"] == "mock"
        assert tool.mock_arguments("看看 https://www.amazon.com/dp/B08XYZ1234 的情况") == {
            "product_url": "https://www.amazon.com/dp/B08XYZ1234"
        }

    def test_real_mode_reports_upstream_errors(self, monkeypatch):
        _, tool = load_tool("solutions.ch24.competitor", "competitor_analysis")
        monkeypatch.setattr(settings, "mock_mode", False)
        monkeypatch.setattr(settings, "scraper_api_key", "k")
        tool.transport = httpx.MockTransport(lambda request: httpx.Response(429))
        assert run(tool.execute(asin="B08XYZ1234")) == {"error": "爬虫服务返回错误：HTTP 429"}


def test_ch24_listing_optimizer():
    _, tool = load_tool("solutions.ch24.listing_optimizer", "listing_optimizer")
    weak = run(tool.execute(title="蓝牙耳机"))
    assert weak["score"] == "1/3" and weak["overall"] == "较差"
    strong = run(
        tool.execute(
            title="Apple AirPods Pro 2 主动降噪无线蓝牙耳机",
            description="支持主动降噪与通透模式，单次续航 6 小时，配合充电盒可达 30 小时，IPX4 防汗防水，一年官方保修。"
            * 2,
        )
    )
    assert strong["score"] == "3/3" and strong["overall"] == "优秀"
    taobao = run(tool.execute(title="降噪" * 31, platform="taobao"))
    assert any("长度限制" in c for c in taobao["checks"])


class TestCh24Calculator:
    @pytest.mark.parametrize(
        ("expression", "result"),
        [("123 * 456", 56088), ("(299 - 50) * 0.85", 211.65), ("2^10", 1024), ("0.1 + 0.2", 0.3), ("-3 + 7 // 2", 0)],
    )
    def test_arithmetic(self, expression, result):
        _, tool = load_tool("solutions.ch24.calculator", "calculator")
        assert run(tool.execute(expression=expression))["result"] == result

    @pytest.mark.parametrize(
        "expression",
        ["__import__('os').system('id')", "9**9**9**9", "1/0", "2 ** 1000", "abs(-1)", "[1, 2]", "1e308 * 10"],
    )
    def test_rejects_anything_else(self, expression):
        _, tool = load_tool("solutions.ch24.calculator", "calculator")
        assert "error" in run(tool.execute(expression=expression))

    def test_end_to_end_in_mock_mode(self):
        load_tool("solutions.ch24.calculator", "calculator")
        events = collect(core.run_agent("123乘以456等于多少？", "c1"))
        result = next(e for e in events if e["type"] == "tool_result")
        assert result["result"] == {"expression": "123*456", "result": 56088}
