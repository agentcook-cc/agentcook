"""Chapter 24: listing advice from plain rules — business logic, no external calls."""

import unicodedata

from app.tools.base import BaseTool
from app.tools.registry import tool_registry

SELLING_POINTS = ("蓝牙", "无线", "降噪", "防水", "续航", "快充", "轻薄", "大容量")


def display_width(text: str) -> int:
    """Wide (CJK) characters count as 2 — how Taobao measures its 60-character title limit."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


class ListingOptimizerTool(BaseTool):
    name = "listing_optimizer"
    description = (
        "检查商品 Listing（标题、描述）并给出优化建议。"
        "当用户给出商品标题或描述、想优化商品页时使用。支持 amazon、taobao、jd。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "商品标题"},
            "description": {"type": "string", "description": "商品描述，可选"},
            "platform": {"type": "string", "enum": ["amazon", "taobao", "jd"], "default": "amazon"},
        },
        "required": ["title"],
    }
    keywords = ("listing", "Listing", "标题", "优化")

    async def execute(self, title: str = "", description: str = "", platform: str = "amazon", **kwargs) -> dict:
        title = title.strip()
        if not title:
            return {"error": "请提供商品标题"}
        checks: list[tuple[bool, str]] = []

        # 1. Title length (Taobao counts width: 60 = 30 Chinese characters).
        too_long = display_width(title) > 60 if platform == "taobao" else len(title) > 200
        if len(title) < 10:
            checks.append((False, "标题太短（少于 10 个字符），建议补充品牌、型号、核心卖点"))
        elif too_long:
            checks.append((False, "标题超出平台长度限制，会被截断，建议精简"))
        else:
            checks.append((True, "标题长度合适"))

        # 2. Selling points in the title.
        found = [word for word in SELLING_POINTS if word in title]
        if found:
            checks.append((True, f"标题包含卖点词：{'、'.join(found)}"))
        else:
            checks.append((False, "标题缺少卖点词，建议加入产品特性（如'降噪'、'续航'）"))

        # 3. Description.
        if not description:
            checks.append((False, "缺少商品描述，建议补充规格、使用场景、售后信息"))
        elif len(description) < 50:
            checks.append((False, "描述太短，建议补充规格、使用场景、售后信息"))
        elif len(description) > 2000:
            checks.append((False, "描述过长，建议分段并突出重点"))
        else:
            checks.append((True, "描述长度合适"))

        tips = []
        if platform == "amazon" and not any(w in title.lower() for w in ("for ", "compatible with", "fits")):
            tips.append("如果是配件，标题里加 'for XXX' / 'compatible with XXX' 能提高搜索匹配")

        passed = sum(ok for ok, _ in checks)
        return {
            "platform": platform,
            "score": f"{passed}/{len(checks)}",
            "checks": [("✅ " if ok else "❌ ") + text for ok, text in checks],
            "tips": tips,
            "overall": "优秀" if passed == len(checks) else "需优化" if passed >= 2 else "较差",
        }


tool_registry.register(ListingOptimizerTool())
