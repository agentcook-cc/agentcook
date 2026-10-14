"""Chapter 24: sales numbers from a real database — read-only, no LLM-written SQL.

The model only picks a metric, a window and an optional category; the SQL
is fixed and parameterised here. Run ``python -m solutions.ch24.seed_sales_db``
first to create demo data.
"""

import asyncio
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from app.config import settings
from app.tools.base import BaseTool
from app.tools.registry import tool_registry

QUERIES = {
    "total_revenue": "SELECT COALESCE(SUM(amount), 0) FROM orders o WHERE o.date BETWEEN ? AND ?",
    "order_count": "SELECT COUNT(*) FROM orders o WHERE o.date BETWEEN ? AND ?",
    "top_products": (
        "SELECT oi.product_name, SUM(oi.quantity) AS qty FROM order_items oi "
        "JOIN orders o ON oi.order_id = o.id WHERE o.date BETWEEN ? AND ?"
    ),
}


class SalesQueryTool(BaseTool):
    name = "sales_query"
    description = (
        "查询店铺的销售数据：总销售额、订单数、热销商品。"
        "当用户询问销售情况、业绩、商品销量时使用。只读，最多查最近 30 天。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": list(QUERIES),
                "description": "total_revenue=总销售额，order_count=订单数，top_products=热销商品",
            },
            "days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 30,
                "default": 7,
                "description": "最近 N 天（含今天）",
            },
            "category": {"type": "string", "description": "可选，按品类筛选，如'耳机'、'手机'"},
        },
        "required": ["metric"],
    }
    keywords = ("销售", "卖了", "销量", "业绩", "订单", "热销")

    def mock_arguments(self, message: str) -> dict:
        metric = (
            "top_products"
            if "最好" in message or "热销" in message
            else "order_count"
            if "订单" in message
            else "total_revenue"
        )
        return {"metric": metric, "days": 1 if "昨天" in message or "今天" in message else 7}

    async def execute(self, metric: str = "", days: int = 7, category: str = "", **kwargs) -> dict:
        if metric not in QUERIES:
            return {"error": f"不支持的指标：{metric}"}
        if not 1 <= int(days) <= 30:
            return {"error": "最多只能查询最近 30 天的数据"}
        if not Path(settings.sales_db_path).exists():
            return {"error": "销售数据库不存在，请先运行 python -m solutions.ch24.seed_sales_db"}
        # sqlite3 blocks; run it off the event loop so other requests keep flowing.
        return await asyncio.to_thread(self._query, metric, int(days), category)

    def _query(self, metric: str, days: int, category: str) -> dict:
        end = date.today()
        start = end - timedelta(days=days - 1)
        sql, params = QUERIES[metric], [start.isoformat(), end.isoformat()]
        if category:
            sql += " AND o.category = ?"
            params.append(category)
        if metric == "top_products":
            sql += " GROUP BY oi.product_name ORDER BY qty DESC LIMIT 5"

        # mode=ro: even a bug here can't modify the data.
        conn = sqlite3.connect(f"file:{Path(settings.sales_db_path).resolve()}?mode=ro", uri=True)
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        base = {"period": f"{start} 至 {end}", "category": category or "全部"}
        if metric == "total_revenue":
            return {"metric": "总销售额", **base, "value": f"¥{rows[0][0]:,.2f}"}
        if metric == "order_count":
            return {"metric": "订单数", **base, "value": rows[0][0]}
        return {"metric": "热销商品TOP 5", **base, "products": [{"name": n, "qty": q} for n, q in rows]}


tool_registry.register(SalesQueryTool())
