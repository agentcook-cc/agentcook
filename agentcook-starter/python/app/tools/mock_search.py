"""web_search — a search tool with canned results, so the demo runs offline.

Swap ``execute`` for a real search API (Tavily, Bing, SerpAPI…) when you go
live; the name, description and parameters can stay exactly as they are.
"""

from app.tools.base import BaseTool
from app.tools.registry import tool_registry

PRESETS: dict[str, list[dict]] = {
    "earbuds": [
        {
            "title": "2026 秋季蓝牙耳机新品盘点：降噪、续航、空间音频三线升级",
            "url": "https://example.com/news/earbuds-autumn",
            "snippet": "主流品牌新品集中在 299-899 元价位，自适应降噪成为标配，单次续航普遍提升到 8 小时以上。",
        },
        {
            "title": "电商平台数据：开放式耳机搜索量同比增长 63%",
            "url": "https://example.com/data/open-ear",
            "snippet": "运动场景带动开放式与骨传导耳机增长，女性用户占比首次超过 45%。",
        },
        {
            "title": "评测：五款 500 元内降噪耳机横评",
            "url": "https://example.com/review/anc-500",
            "snippet": "通话降噪和佩戴舒适度是差评的主要来源，低延迟游戏模式成为新卖点。",
        },
    ],
    "competitor": [
        {
            "title": "竞品A 定价策略拆解：主力款 399 元，大促到手价 329 元",
            "url": "https://example.com/analysis/competitor-a",
            "snippet": "竞品A 以'高配低价'切入，主力款毛利约 35%，依靠满减和以旧换新拉动转化。",
        },
        {
            "title": "竞品A 近 30 天销量与评价趋势",
            "url": "https://example.com/data/competitor-a-30d",
            "snippet": "月销约 2.1 万件，好评率 94%，差评集中在'连接不稳定'和'充电盒易刮花'。",
        },
        {
            "title": "同价位段价格带分布",
            "url": "https://example.com/data/price-band",
            "snippet": "300-400 元价位竞争最激烈，头部 5 个品牌占据 58% 销量。",
        },
    ],
    "default": [
        {
            "title": "跨境电商运营 2026 趋势报告",
            "url": "https://example.com/report/2026-trends",
            "snippet": "AI 选品与自动化客服普及率超过 40%，内容电商渠道占比继续上升。",
        },
        {
            "title": "如何用数据驱动 Listing 优化",
            "url": "https://example.com/guide/listing-data",
            "snippet": "标题关键词、主图点击率和评价数是影响转化的三大因素。",
        },
    ],
}


def _preset_for(query: str) -> str:
    if any(word in query for word in ("耳机", "earbud", "headphone")):
        return "earbuds"
    if any(word in query for word in ("竞品", "竞争", "对手", "competitor")):
        return "competitor"
    return "default"


class MockSearchTool(BaseTool):
    name = "web_search"
    description = (
        "搜索互联网获取最新信息。当需要查找实时数据、新品动态、竞品信息、市场趋势时使用。"
        "返回若干条结果（标题、链接、摘要）。"
    )
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "搜索关键词，越具体越好"}},
        "required": ["query"],
    }
    keywords = ("搜索", "搜一下", "查一下", "最新", "新品", "竞品", "趋势", "search")

    async def execute(self, query: str = "", **kwargs) -> dict:
        if not query.strip():
            return {"error": "query 不能为空"}
        return {"query": query, "source": "mock", "results": PRESETS[_preset_for(query)]}


tool_registry.register(MockSearchTool())
