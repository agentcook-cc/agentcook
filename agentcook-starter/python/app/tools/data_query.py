"""data_query — read-only queries over (demo) store data.

The agent never writes SQL: it picks a metric and a time window, and this
tool decides what actually runs. Replace ``_load`` with your database.
"""

from datetime import date, timedelta

from app.tools.base import BaseTool
from app.tools.registry import tool_registry

PRODUCTS = [
    ("蓝牙耳机 Pro", "耳机", 299.0),
    ("开放式运动耳机", "耳机", 459.0),
    ("快充充电器 65W", "配件", 129.0),
    ("手机壳 磨砂款", "配件", 39.0),
]


def _load(days: int) -> list[dict]:
    """Deterministic demo orders: a few per product per day, newest first."""
    today = date.today()
    rows = []
    for offset in range(days):
        day = today - timedelta(days=offset)
        for index, (name, category, price) in enumerate(PRODUCTS):
            qty = (day.toordinal() * (index + 3)) % 7 + 1
            rows.append({"date": day.isoformat(), "product": name, "category": category, "qty": qty, "price": price})
    return rows


class DataQueryTool(BaseTool):
    name = "data_query"
    description = (
        "查询本店的销售数据：总销售额、订单量、热销商品。"
        "当用户问业绩、卖了多少、哪个商品卖得好时使用。只读，最多查最近 30 天。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["total_revenue", "order_count", "top_products"],
                "description": "total_revenue=销售额，order_count=订单量，top_products=热销商品",
            },
            "days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7, "description": "最近 N 天"},
            "category": {"type": "string", "description": "可选，按品类筛选，如'耳机'、'配件'"},
        },
        "required": ["metric"],
    }
    keywords = ("销售", "卖了", "卖得", "销量", "业绩", "订单", "热销", "营收")

    def mock_arguments(self, message: str) -> dict:
        if any(word in message for word in ("热销", "卖得最好", "排行", "top")):
            metric = "top_products"
        elif "订单" in message:
            metric = "order_count"
        else:
            metric = "total_revenue"
        days = 1 if "昨天" in message or "今天" in message else 30 if "30" in message or "月" in message else 7
        category = next((c for c in ("耳机", "配件") if c in message), "")
        return {"metric": metric, "days": days, **({"category": category} if category else {})}

    async def execute(self, metric: str = "", days: int = 7, category: str = "", **kwargs) -> dict:
        if not 1 <= int(days) <= 30:
            return {"error": "days 必须在 1 到 30 之间"}
        rows = [r for r in _load(int(days)) if not category or r["category"] == category]
        period = {"days": int(days), "category": category or "全部"}
        if metric == "total_revenue":
            return {"metric": "销售额", **period, "value": round(sum(r["qty"] * r["price"] for r in rows), 2)}
        if metric == "order_count":
            return {"metric": "订单量", **period, "value": sum(r["qty"] for r in rows)}
        if metric == "top_products":
            totals: dict[str, int] = {}
            for r in rows:
                totals[r["product"]] = totals.get(r["product"], 0) + r["qty"]
            top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
            return {"metric": "热销商品", **period, "products": [{"name": n, "qty": q} for n, q in top]}
        return {"error": f"不支持的指标：{metric}"}


tool_registry.register(DataQueryTool())
