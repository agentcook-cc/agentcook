"""Chapter 23 exercise: your first tool — a mock weather lookup."""

from app.tools.base import BaseTool
from app.tools.registry import tool_registry

MOCK_WEATHER = {
    "北京": {"temp": "28°C", "weather": "晴", "humidity": "45%", "wind": "北风3级"},
    "上海": {"temp": "31°C", "weather": "多云", "humidity": "72%", "wind": "东南风2级"},
    "深圳": {"temp": "33°C", "weather": "雷阵雨", "humidity": "85%", "wind": "南风4级"},
}
DEFAULT_WEATHER = {"temp": "25°C", "weather": "晴", "humidity": "50%", "wind": "微风"}


def find_city(message: str, default: str = "北京") -> str:
    """Pick a known city out of a sentence (mock mode only — real LLMs extract it themselves)."""
    return next((city for city in MOCK_WEATHER if city in message), default)


class WeatherTool(BaseTool):
    name = "weather_query"
    description = "查询指定城市的天气信息。当用户询问天气、气温、穿衣建议时使用。"
    parameters = {
        "type": "object",
        "properties": {"city": {"type": "string", "description": "城市名称，如'北京'、'上海'"}},
        "required": ["city"],
    }
    keywords = ("天气", "气温", "下雨", "穿什么")

    def mock_arguments(self, message: str) -> dict:
        return {"city": find_city(message)}

    async def execute(self, city: str = "", **kwargs) -> dict:
        if not city:
            return {"error": "请提供城市名称"}
        return {"city": city, "source": "mock", **MOCK_WEATHER.get(city, DEFAULT_WEATHER)}


tool_registry.register(WeatherTool())
