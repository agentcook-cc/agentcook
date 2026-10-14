"""Settings parsing/validation and the built-in toolkits."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentcook_app import toolkits as tk
from agentcook_app.config import DEV_JWT_SECRET, ConfigError, Settings
from agentcook_app.services import InMemoryAgentRuntime

pytestmark = pytest.mark.unit


class TestSettings:
    def test_defaults_are_safe_for_local_dev(self) -> None:
        s = Settings.from_env({})
        assert s.env == "development"
        assert s.llm_provider == "mock" and s.uses_mock_model
        assert s.auth_mode == "optional"
        assert s.storage == "memory"
        assert s.jwt_secret == DEV_JWT_SECRET
        assert s.otel_endpoint is None

    def test_provider_chain_and_legacy_mock_flag(self) -> None:
        s = Settings.from_env(
            {"AGENTCOOK_LLM_PROVIDER": "qwen", "AGENTCOOK_LLM_FALLBACKS": "zhipu, mock"}
        )
        assert s.llm_provider == "qwen,zhipu,mock" and not s.uses_mock_model
        forced = Settings.from_env(
            {"AGENTCOOK_LLM_PROVIDER": "qwen", "AGENTCOOK_CHAT_MOCK": "true"}
        )
        assert forced.llm_provider == "mock"

    def test_java_secret_name_is_accepted(self) -> None:
        s = Settings.from_env({"AGENTCOOK_AUTH_JWT_SECRET": "x" * 40})
        assert s.jwt_secret == "x" * 40

    def test_public_key_switches_to_rs256(self) -> None:
        s = Settings.from_env({"AGENTCOOK_JWT_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----"})
        assert s.jwt_algorithm == "RS256"

    def test_storage_inference(self) -> None:
        s = Settings.from_env({"AGENTCOOK_DATABASE_URL": "postgresql://u:p@h/db"})
        assert s.storage == "postgres" and s.db_auto_migrate
        with pytest.raises(ConfigError, match="requires AGENTCOOK_DATABASE_URL"):
            Settings.from_env({"AGENTCOOK_STORAGE": "postgres"})

    def test_extra_skill_dirs(self, tmp_path: Path) -> None:
        import os

        s = Settings.from_env({"AGENTCOOK_SKILLS_DIRS": f"{tmp_path}{os.pathsep}{tmp_path}/b"})
        assert s.skills_dirs[1:] == (tmp_path, tmp_path / "b")

    @pytest.mark.parametrize(
        "env,message",
        [
            ({"AGENTCOOK_ENV": "staging"}, "AGENTCOOK_ENV"),
            ({"AGENTCOOK_AUTH_MODE": "maybe"}, "AGENTCOOK_AUTH_MODE"),
            ({"AGENTCOOK_STORAGE": "s3"}, "AGENTCOOK_STORAGE"),
            ({"AGENTCOOK_MAX_TURNS": "0"}, "MAX_TURNS"),
        ],
    )
    def test_invalid_values(self, env: dict[str, str], message: str) -> None:
        with pytest.raises(ConfigError, match=message):
            Settings.from_env(env)

    def test_production_refuses_unsafe_configuration(self) -> None:
        with pytest.raises(ConfigError, match="development secret"):
            Settings.from_env({"AGENTCOOK_ENV": "production"})
        with pytest.raises(ConfigError, match="AUTH_MODE=required"):
            Settings.from_env(
                {
                    "AGENTCOOK_ENV": "prod",
                    "AGENTCOOK_AUTH_MODE": "optional",
                    "AGENTCOOK_JWT_SECRET": "y" * 40,
                }
            )
        with pytest.raises(ConfigError, match="32 bytes"):
            Settings.from_env({"AGENTCOOK_ENV": "production", "AGENTCOOK_JWT_SECRET": "short"})
        ok = Settings.from_env({"AGENTCOOK_ENV": "production", "AGENTCOOK_JWT_SECRET": "z" * 40})
        assert ok.is_production and ok.auth_mode == "required" and not ok.db_auto_migrate


class TestCommerceDemoTools:
    async def test_web_search_ranks_relevant_docs(self) -> None:
        result = await tk.web_search.invoke({"query": "bluetooth earbuds pricing"})
        assert result.success
        titles = [r["title"] for r in result.output["results"]]
        assert titles and "earbuds" in titles[0].lower()
        assert "demo" in result.output["source"]

    async def test_web_search_chinese_query(self) -> None:
        result = await tk.web_search.invoke({"query": "蓝牙耳机竞品定价"})
        assert result.output["results"]

    async def test_sales_query(self) -> None:
        all_rows = (await tk.sales_query.invoke({})).output["rows"]
        assert {r["product_id"] for r in all_rows} == {"earbuds-pro", "earbuds-lite", "blender-go"}
        week = (await tk.sales_query.invoke({"product": "earbuds-pro", "period": "7d"})).output
        assert week["rows"][0]["units"] == round(1840 * 7 / 30)
        bad = await tk.sales_query.invoke({"product": "nope"})
        assert not bad.success and "known:" in (bad.error or "")
        bad_period = await tk.sales_query.invoke({"period": "1y"})
        assert not bad_period.success

    async def test_competitor_prices(self) -> None:
        out = (await tk.competitor_prices.invoke({"category": "earbuds"})).output
        assert out["price_range_usd"] == [24.99, 79.99]
        assert out["median_price_usd"] == 59.99


class TestFetchUrlGuard:
    @pytest.mark.parametrize(
        "url,message",
        [
            ("ftp://example.com/x", "only http(s)"),
            ("http://user:pass@example.com/", "embedded credentials"),
            ("http:///nohost", "no host"),
        ],
    )
    async def test_rejects_bad_urls(self, url: str, message: str) -> None:
        result = await tk.fetch_url.invoke({"url": url})
        assert not result.success and message in (result.error or "")

    @pytest.mark.parametrize(
        "address",
        ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "0.0.0.0"],
    )
    async def test_blocks_private_addresses(
        self, monkeypatch: pytest.MonkeyPatch, address: str
    ) -> None:
        monkeypatch.setattr(
            tk.socket, "getaddrinfo", lambda host, port: [(None, None, None, None, (address, 0))]
        )
        result = await tk.fetch_url.invoke({"url": "http://internal.example/"})
        assert not result.success and "private" in (result.error or "")

    async def test_fetches_and_extracts_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        monkeypatch.setattr(
            tk.socket,
            "getaddrinfo",
            lambda host, port: [(None, None, None, None, ("93.184.216.34", 0))],
        )
        page = (
            "<html><head><title>Demo &amp; Co</title><style>x{}</style></head>"
            "<body><h1>Hello</h1><script>evil()</script><p>World</p></body></html>"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/redirect":
                return httpx.Response(302, headers={"location": "/page"})
            return httpx.Response(
                200, text=page, headers={"content-type": "text/html; charset=utf-8"}
            )

        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            tk.httpx,
            "AsyncClient",
            lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
        )
        result = await tk.fetch_url.invoke(
            {"url": "https://example.com/redirect", "max_chars": 500}
        )
        assert result.success, result.error
        assert result.output["title"] == "Demo & Co"
        assert result.output["url"].endswith("/page")
        assert "Hello" in result.output["text"] and "World" in result.output["text"]
        assert "evil" not in result.output["text"]


class TestMemoryTools:
    async def test_remember_and_recall(self) -> None:
        from agentcook_core import IdentityCard

        runtime = InMemoryAgentRuntime()
        await runtime.ensure_agent(
            "a-1",
            IdentityCard(name="A", role="r", created_at="2026-01-01T00:00:00+00:00"),
            user_id="u",
        )
        remember, recall = tk.make_memory_tools(runtime, "a-1")
        assert (await remember.invoke({"content": "Prefers metric units"})).success
        assert not (await remember.invoke({"content": "  "})).success
        hits = (await recall.invoke({"query": "which units?"})).output["memories"]
        assert hits[0]["content"] == "Prefers metric units"
        assert await runtime.get_owner("a-1") == "u"
