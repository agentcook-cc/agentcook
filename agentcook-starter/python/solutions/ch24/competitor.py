"""Chapter 24: competitor analysis through a third-party scraping service.

Real mode needs ``SCRAPER_API_KEY`` (ScraperAPI) and ``pip install beautifulsoup4``.
Without a key (or in mock mode) it returns clearly-labelled demo data.
"""

import re

import httpx

from app.config import settings
from app.tools.base import BaseTool
from app.tools.registry import tool_registry

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
URL_RE = re.compile(r"https?://[^\s，。]+")


class CompetitorAnalysisTool(BaseTool):
    name = "competitor_analysis"
    description = (
        "抓取并分析竞品商品页：价格、评分、评论数、库存。"
        "当用户给出竞品链接或亚马逊 ASIN、想了解竞品表现时使用。product_url 和 asin 至少提供一个。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "product_url": {"type": "string", "description": "竞品商品页 URL（亚马逊、淘宝、京东等）"},
            "asin": {"type": "string", "description": "亚马逊 ASIN，10 位大写字母或数字"},
        },
        "required": [],
    }
    keywords = ("amazon.com", "ASIN", "asin", "竞品链接")
    transport: httpx.AsyncBaseTransport | None = None

    def mock_arguments(self, message: str) -> dict:
        url = URL_RE.search(message)
        return {"product_url": url.group(0)} if url else {"asin": "B0EXAMPLE1"}

    async def execute(self, product_url: str = "", asin: str = "", **kwargs) -> dict:
        if asin and not ASIN_RE.match(asin):
            return {"error": "ASIN 格式不对：应为 10 位大写字母或数字"}
        if product_url and not product_url.startswith(("http://", "https://")):
            return {"error": "product_url 必须是 http(s) 链接"}
        if not product_url and not asin:
            return {"error": "请提供竞品 URL 或 ASIN"}
        target = product_url or f"https://www.amazon.com/dp/{asin}"

        if settings.mock_mode or not settings.scraper_api_key:
            return {
                "product_url": target,
                "price": "$39.99",
                "rating": 4.4,
                "review_count": 1873,
                "availability": "In Stock",
                "source": "mock",
            }

        try:
            async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
                resp = await client.get(
                    "https://api.scraperapi.com/", params={"api_key": settings.scraper_api_key, "url": target}
                )
        except httpx.TimeoutException:
            return {"error": "爬虫请求超时，请稍后重试"}
        except httpx.HTTPError as exc:
            return {"error": f"爬虫服务连接失败：{exc}"}
        if resp.status_code != 200:
            return {"error": f"爬虫服务返回错误：HTTP {resp.status_code}"}
        return {"product_url": target, **parse_product_page(resp.text), "source": "scraper_api"}


def parse_product_page(html: str) -> dict:
    """Pull price / rating / reviews / stock out of an Amazon-style product page."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:  # optional dependency, only needed in real mode
        return {"error": "缺少依赖：pip install beautifulsoup4"}

    soup = BeautifulSoup(html, "html.parser")

    def text(selector: str) -> str:
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else ""

    rating = re.search(r"\d+(?:\.\d+)?", text("#acrPopover .a-icon-alt, .a-icon-star .a-icon-alt"))
    reviews = re.search(r"[\d,]+", text("#acrCustomerReviewText"))
    return {
        "price": text(".a-price .a-offscreen, #priceblock_ourprice") or "价格未知",
        "rating": float(rating.group(0)) if rating else None,
        "review_count": int(reviews.group(0).replace(",", "")) if reviews else 0,
        "availability": text("#availability span") or "库存状态未知",
    }


tool_registry.register(CompetitorAnalysisTool())
