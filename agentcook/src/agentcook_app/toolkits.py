"""Toolkits — named, executable tool bundles the runtime can attach to agents.

A *toolkit* is what a chat request's ``plugin_ids`` (and an agent spec's
``toolkits:``) refers to. Unlike the plugin catalog in agentcook-java
(installable packages, connectors, permissions), a toolkit here is
something this process can actually execute right now.

Built-in toolkits:

- ``core``           — ``current_time``, ``calculator``.
- ``web``            — ``fetch_url`` (real HTTP, SSRF-guarded, size-capped).
- ``commerce-demo``  — ``web_search`` / ``sales_query`` / ``competitor_prices``
  over a bundled demo dataset (cross-border e-commerce, the tutorial's
  running example). Clearly labelled as demo data in every result.

Per-user tools (``remember`` / ``recall``) are built per request by
:func:`make_memory_tools` because they close over the caller's agent
instance.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import ipaddress
import re
import socket
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import httpx
from agentcook_core import MemoryEvent, ToolProtocol
from agentcook_core.builtin_tools import calculator, current_time
from agentcook_core.tools import FunctionTool, ToolInputError, tool

from agentcook_app.services import AgentRuntime


@dataclass(frozen=True, slots=True)
class Toolkit:
    id: str
    name: str
    description: str
    tools: tuple[ToolProtocol, ...]

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tools": [
                {"name": t.name, "description": t.description, "parameters": t.parameters_schema}
                for t in self.tools
            ],
        }


class ToolkitRegistry:
    def __init__(self, toolkits: Iterable[Toolkit] = ()) -> None:
        self._toolkits: dict[str, Toolkit] = {}
        for kit in toolkits:
            self.register(kit)

    def register(self, kit: Toolkit) -> None:
        if kit.id in self._toolkits:
            raise ValueError(f"toolkit {kit.id!r} already registered")
        self._toolkits[kit.id] = kit

    def get(self, toolkit_id: str) -> Toolkit | None:
        return self._toolkits.get(toolkit_id)

    def resolve(self, ids: Iterable[str]) -> tuple[list[ToolProtocol], list[str]]:
        """Return (tools, unknown_ids) for the requested toolkit ids."""
        tools: list[ToolProtocol] = []
        unknown: list[str] = []
        for toolkit_id in ids:
            kit = self._toolkits.get(toolkit_id)
            if kit is None:
                unknown.append(toolkit_id)
            else:
                tools.extend(kit.tools)
        return tools, unknown

    def list(self) -> list[Toolkit]:
        return list(self._toolkits.values())

    def __contains__(self, toolkit_id: object) -> bool:
        return toolkit_id in self._toolkits


# ---------------------------------------------------------------------------
# web — fetch_url with SSRF protection
# ---------------------------------------------------------------------------

_MAX_BYTES = 1_000_000
_FETCH_TIMEOUT = 10.0


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "head", "template"}
    _BLOCK = {
        "p",
        "div",
        "br",
        "li",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "section",
        "article",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        return re.sub(r"\n\s*\n+", "\n\n", raw).strip()


def _is_public_address(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return False
    return True


async def _guard_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ToolInputError("only http(s) URLs are allowed")
    if not parsed.hostname:
        raise ToolInputError("URL has no host")
    if parsed.username or parsed.password:
        raise ToolInputError("URLs with embedded credentials are not allowed")
    public = await asyncio.to_thread(_is_public_address, parsed.hostname)
    if not public:
        raise ToolInputError("refusing to fetch a private, loopback or unresolvable address")
    return parsed.geturl()


async def _fetch(url: str, max_chars: int) -> dict[str, Any]:
    target = await _guard_url(url)
    async with httpx.AsyncClient(
        timeout=_FETCH_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": "agentcook-fetch/2.0 (+https://github.com/agentcook-cc/agentcook)"},
    ) as client:
        for _ in range(5):  # follow redirects manually so each hop is SSRF-checked
            async with client.stream("GET", target) as response:
                if response.is_redirect and response.headers.get("location"):
                    target = await _guard_url(str(response.url.join(response.headers["location"])))
                    continue
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_BYTES:
                        break
                content_type = response.headers.get("content-type", "")
                text = body.decode(response.encoding or "utf-8", errors="replace")
                title = ""
                if "html" in content_type or text.lstrip()[:15].lower().startswith(
                    ("<!doctype", "<html")
                ):
                    parser = _TextExtractor()
                    parser.feed(text)
                    title, text = html.unescape(parser.title.strip()), parser.text()
                truncated = len(text) > max_chars
                return {
                    "url": str(response.url),
                    "status": response.status_code,
                    "content_type": content_type.split(";")[0],
                    "title": title,
                    "text": text[:max_chars],
                    "truncated": truncated,
                }
    raise ToolInputError("too many redirects")


@tool(timeout=20)
async def fetch_url(
    url: Annotated[str, "Absolute http(s) URL to read"],
    max_chars: Annotated[int, "Maximum characters of page text to return (500-20000)"] = 6_000,
) -> dict[str, Any]:
    """Fetch a public web page and return its readable text.

    Use this to read a specific URL the user gives you or that you found.
    Private network addresses are blocked.
    """
    return await _fetch(url, max(500, min(int(max_chars), 20_000)))


# ---------------------------------------------------------------------------
# commerce-demo — bundled demo dataset (tutorial running example)
# ---------------------------------------------------------------------------

_DEMO_NOTE = "demo dataset bundled with agentcook — not live market data"

_CORPUS: tuple[dict[str, str], ...] = (
    {
        "title": "TWS earbuds 2026 trends: ANC under $50 becomes table stakes",
        "snippet": "Active noise cancellation is now expected in budget true-wireless earbuds; "
        "battery life (8h+ per charge) and multipoint pairing are the top review keywords.",
        "url": "https://example.com/market/tws-2026",
        "tags": "earbuds bluetooth tws headphones 蓝牙耳机 耳机 趋势",
    },
    {
        "title": "Amazon US Q3: portable blenders search volume +38% YoY",
        "snippet": "USB-C rechargeable portable blenders keep growing; negative reviews focus on "
        "seal leakage and blade torque.",
        "url": "https://example.com/market/portable-blender-q3",
        "tags": "blender kitchen 榨汁机 便携 amazon",
    },
    {
        "title": "Competitor teardown: SoundCore-style earbuds pricing ladder",
        "snippet": "Leading brands ladder SKUs at $29 / $49 / $79; the $49 tier carries "
        "ANC + app EQ "
        "and has the best conversion.",
        "url": "https://example.com/competitors/earbuds-pricing",
        "tags": "competitor pricing earbuds 竞品 定价 蓝牙耳机",
    },
    {
        "title": "Listing optimization: titles with use-case keywords convert 12% better",
        "snippet": "Front-load the core keyword, add 2 use-case phrases (gym, commute), keep under "
        "200 characters; bullet points should lead with benefits, not specs.",
        "url": "https://example.com/playbooks/listing-titles",
        "tags": "listing seo title 标题 优化 listing优化",
    },
    {
        "title": "Cross-border logistics: EU VAT changes for low-value parcels",
        "snippet": "IOSS registration simplifies VAT collection for consignments under €150; "
        "sellers without IOSS see higher return rates from customs fees.",
        "url": "https://example.com/compliance/eu-ioss",
        "tags": "eu vat ioss logistics compliance 跨境 物流 欧盟",
    },
)

_SALES: dict[str, dict[str, Any]] = {
    "earbuds-pro": {
        "name": "AuraBuds Pro (ANC earbuds)",
        "price": 49.99,
        "units_30d": 1840,
        "return_rate": 0.041,
        "rating": 4.4,
        "trend": "+12%",
    },
    "earbuds-lite": {
        "name": "AuraBuds Lite",
        "price": 29.99,
        "units_30d": 3120,
        "return_rate": 0.063,
        "rating": 4.1,
        "trend": "+3%",
    },
    "blender-go": {
        "name": "BlendGo portable blender",
        "price": 34.99,
        "units_30d": 960,
        "return_rate": 0.088,
        "rating": 3.9,
        "trend": "+27%",
    },
}

_COMPETITORS: dict[str, list[dict[str, Any]]] = {
    "earbuds": [
        {"brand": "SoundCore A40", "price": 59.99, "anc": True, "battery_h": 10, "rating": 4.5},
        {"brand": "JLab Go Air Pop", "price": 24.99, "anc": False, "battery_h": 8, "rating": 4.3},
        {"brand": "EarFun Air Pro 4", "price": 79.99, "anc": True, "battery_h": 11, "rating": 4.6},
    ],
    "blender": [
        {"brand": "BlendJet 2", "price": 49.99, "capacity_oz": 16, "rating": 4.4},
        {"brand": "Ninja Blast", "price": 59.99, "capacity_oz": 18, "rating": 4.6},
    ],
}

_PERIOD_FACTOR = {"7d": 7 / 30, "30d": 1.0, "90d": 3.0}


def _score(doc: dict[str, str], terms: Sequence[str]) -> int:
    haystack = f"{doc['title']} {doc['snippet']} {doc['tags']}".lower()
    return sum(haystack.count(t) for t in terms)


def _terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", query.lower())
    cjk = re.findall(r"[一-鿿]{2,}", query)
    grams = [run[i : i + 2] for run in cjk for i in range(len(run) - 1)]
    return [w for w in words if len(w) > 2] + grams


@tool
def web_search(
    query: Annotated[str, "Search keywords"],
    max_results: Annotated[int, "Number of results (1-5)"] = 3,
) -> dict[str, Any]:
    """Search market news and e-commerce playbooks (bundled demo index).

    Use for trends, competitor news and listing best practices.
    """
    terms = _terms(query)
    ranked = sorted(_CORPUS, key=lambda d: _score(d, terms), reverse=True)
    hits = [d for d in ranked if _score(d, terms) > 0][: max(1, min(max_results, 5))]
    return {
        "query": query,
        "source": _DEMO_NOTE,
        "results": [{k: d[k] for k in ("title", "snippet", "url")} for d in hits],
    }


@tool
def sales_query(
    product: Annotated[
        str | None, "Product id (earbuds-pro, earbuds-lite, blender-go); omit for all"
    ] = None,
    period: Literal["7d", "30d", "90d"] = "30d",
) -> dict[str, Any]:
    """Look up unit sales, price, return rate and rating for our store's products."""
    factor = _PERIOD_FACTOR[period]
    if product is not None and product not in _SALES:
        raise ToolInputError(f"unknown product {product!r}; known: {', '.join(_SALES)}")
    rows = []
    for pid, row in _SALES.items():
        if product and pid != product:
            continue
        units = round(row["units_30d"] * factor)
        rows.append(
            {
                "product_id": pid,
                "name": row["name"],
                "price_usd": row["price"],
                "units": units,
                "revenue_usd": round(units * row["price"], 2),
                "return_rate": row["return_rate"],
                "rating": row["rating"],
                "trend_vs_prev_period": row["trend"],
            }
        )
    return {
        "period": period,
        "as_of": dt.date.today().isoformat(),
        "source": _DEMO_NOTE,
        "rows": rows,
    }


@tool
def competitor_prices(
    category: Annotated[Literal["earbuds", "blender"], "Product category"],
) -> dict[str, Any]:
    """Compare competitor products and prices in a category."""
    rows = _COMPETITORS[category]
    prices = [r["price"] for r in rows]
    return {
        "category": category,
        "source": _DEMO_NOTE,
        "competitors": rows,
        "price_range_usd": [min(prices), max(prices)],
        "median_price_usd": sorted(prices)[len(prices) // 2],
    }


# ---------------------------------------------------------------------------
# memory — per-user long-term memory (ADR-011 layer 3)
# ---------------------------------------------------------------------------


def make_memory_tools(runtime: AgentRuntime, agent_instance_id: str) -> list[FunctionTool]:
    """``remember`` / ``recall`` bound to one agent instance's memory."""

    async def remember(
        content: Annotated[str, "The fact or preference to remember, as one short sentence"],
        kind: Literal["observation", "decision", "reflection"] = "observation",
    ) -> dict[str, Any]:
        text = content.strip()
        if not text:
            raise ToolInputError("content must not be empty")
        if len(text) > 2_000:
            raise ToolInputError("content too long (max 2000 characters)")
        stored = await runtime.append_memory_event(
            agent_instance_id,
            MemoryEvent(
                timestamp=dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds"),
                kind=kind,
                content=text,
                source="agent.remember",
            ),
        )
        return {"saved": True, "id": stored.id}

    async def recall(
        query: Annotated[str, "What to look up in long-term memory"],
        top_k: Annotated[int, "Max memories to return (1-10)"] = 5,
    ) -> dict[str, Any]:
        result = await runtime.search_memory(agent_instance_id, query, top_k=max(1, min(top_k, 10)))
        return {
            "query": query,
            "memories": [{"content": h.content, "score": round(h.score, 3)} for h in result.hits],
        }

    return [
        FunctionTool(
            remember,
            description=(
                "Save a durable fact about the user or task to long-term memory "
                "(preferences, decisions, important details). Use sparingly."
            ),
        ),
        FunctionTool(
            recall,
            description="Search long-term memory for facts saved in earlier conversations.",
        ),
    ]


def builtin_toolkits() -> ToolkitRegistry:
    return ToolkitRegistry(
        [
            Toolkit(
                id="core",
                name="Core utilities",
                description="Current time and exact arithmetic.",
                tools=(current_time, calculator),
            ),
            Toolkit(
                id="web",
                name="Web reader",
                description="Fetch and read public web pages (SSRF-guarded).",
                tools=(fetch_url,),
            ),
            Toolkit(
                id="commerce-demo",
                name="Commerce demo data",
                description=(
                    "Market search, store sales and competitor prices over a bundled "
                    "cross-border e-commerce demo dataset."
                ),
                tools=(web_search, sales_query, competitor_prices),
            ),
        ]
    )


__all__ = [
    "Toolkit",
    "ToolkitRegistry",
    "builtin_toolkits",
    "competitor_prices",
    "fetch_url",
    "make_memory_tools",
    "sales_query",
    "web_search",
]
