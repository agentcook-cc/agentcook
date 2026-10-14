"""Chapter 24: weather from a real API (QWeather), mock data when not configured.

Setup: create a project in the QWeather console, then put its API key and
API Host (looks like ``abc1234xyz.re.qweatherapi.com``) in ``.env``:

    QWEATHER_API_KEY=...
    QWEATHER_API_HOST=...
"""

import logging

import httpx

from app.config import settings
from app.tools.base import BaseTool
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

MOCK_WEATHER = {
    "北京": {"temp": "28°C", "weather": "晴", "humidity": "45%", "wind": "北风3级"},
    "上海": {"temp": "31°C", "weather": "多云", "humidity": "72%", "wind": "东南风2级"},
    "深圳": {"temp": "33°C", "weather": "雷阵雨", "humidity": "85%", "wind": "南风4级"},
}
DEFAULT_WEATHER = {"temp": "25°C", "weather": "晴", "humidity": "50%", "wind": "微风"}


class WeatherTool(BaseTool):
    name = "weather_query"
    description = (
        "查询指定城市的实时天气。当用户询问天气、气温、湿度、风力、穿衣建议时使用。"
        "只有当前天气：不支持历史天气，也不支持未来预报。"
    )
    parameters = {
        "type": "object",
        "properties": {"city": {"type": "string", "description": "城市名称，如'北京'、'上海'、'深圳'"}},
        "required": ["city"],
    }
    keywords = ("天气", "气温", "下雨", "穿什么")
    transport: httpx.AsyncBaseTransport | None = None  # tests swap in a fake HTTP transport

    def mock_arguments(self, message: str) -> dict:
        return {"city": next((city for city in MOCK_WEATHER if city in message), "北京")}

    async def execute(self, city: str = "", **kwargs) -> dict:
        if not city:
            return {"error": "请提供城市名称"}
        # Step 1 of the migration: keep the mock switch.
        if settings.mock_mode or not (settings.qweather_api_key and settings.qweather_api_host):
            return {"city": city, "source": "mock", **MOCK_WEATHER.get(city, DEFAULT_WEATHER)}
        try:
            return await self._query(city)
        except httpx.HTTPError as exc:
            # Degrade honestly: tell the model the service is down rather than
            # passing off demo numbers as today's weather.
            logger.warning("qweather failed: %r", exc)
            return {"error": "天气服务暂时不可用，请稍后再试"}

    async def _query(self, city: str) -> dict:
        async with httpx.AsyncClient(
            base_url=f"https://{settings.qweather_api_host}",
            headers={"X-QW-Api-Key": settings.qweather_api_key},  # key in a header, not in the URL/logs
            timeout=10,
            transport=self.transport,
        ) as client:
            geo = (await client.get("/geo/v2/city/lookup", params={"location": city, "number": 1})).json()
            if geo.get("code") != "200" or not geo.get("location"):
                return {"error": f"未找到城市：{city}"}
            location = geo["location"][0]

            data = (await client.get("/v7/weather/now", params={"location": location["id"]})).json()
            if data.get("code") != "200":
                return {"error": f"天气查询失败（code={data.get('code')}）"}
            now = data["now"]
            return {
                "city": location.get("name", city),
                "temp": f"{now['temp']}°C",
                "weather": now["text"],
                "humidity": f"{now['humidity']}%",
                "wind": f"{now['windDir']}{now['windScale']}级",
                "observed_at": now.get("obsTime"),
                "source": "qweather",
            }


tool_registry.register(WeatherTool())
