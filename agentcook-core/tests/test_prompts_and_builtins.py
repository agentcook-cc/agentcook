"""Tests for prompts.py, tokens.py and builtin_tools.py."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from agentcook_core import IdentityCard, SkillManifest, SoulConfig
from agentcook_core.builtin_tools import calculator, current_time, make_load_skill_tool
from agentcook_core.prompts import PromptSection, SystemPromptBuilder, build_agent_system_prompt
from agentcook_core.skill_loader import SkillRegistry
from agentcook_core.tokens import estimate_tokens

pytestmark = pytest.mark.unit


def test_builder_puts_dynamic_sections_last_and_skips_empty() -> None:
    b = SystemPromptBuilder()
    b.add("Dynamic", "today", cacheable=False)
    b.add("Stable", "rules")
    b.add("Empty", "   ")
    assert b.build() == "## Stable\nrules\n\n## Dynamic\ntoday"


def test_agent_system_prompt_layout() -> None:
    prompt = build_agent_system_prompt(
        instructions="You help sellers.",
        identity=IdentityCard(name="Cook", role="assistant", created_at="x", scopes=frozenset({"b", "a"})),
        soul=SoulConfig(tone="warm", values=("honesty",), custom_traits={"emoji": "rarely"}),
        skills=[SkillManifest(name="zeta", description="Z"), SkillManifest(name="alpha", description="A")],
        memories=["User prefers metric units."],
        now=dt.datetime(2026, 10, 14, 23, 59, tzinfo=dt.UTC),
    )
    assert prompt.startswith("You help sellers.")
    assert "You are Cook, acting as: assistant." in prompt
    assert "Your authorized scopes: a, b." in prompt
    assert "Tone: warm." in prompt and "emoji: rarely" in prompt
    assert prompt.index("`alpha`") < prompt.index("`zeta`")
    # dynamic content goes last, at day granularity
    assert prompt.index("## Skills") < prompt.index("## Relevant memories") < prompt.index("## Context")
    assert prompt.endswith("Today's date (UTC): 2026-10-14.")


def test_extra_sections_respect_cacheability() -> None:
    prompt = build_agent_system_prompt(
        extra_sections=[PromptSection("Volatile", "v", cacheable=False), PromptSection("Policy", "p")],
        operating_rules=None,
        now=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    )
    assert prompt.index("## Policy") < prompt.index("## Volatile") < prompt.index("## Context")


def test_estimate_tokens_counts_cjk_individually() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("你好世界") == 4
    assert estimate_tokens("hi 你好") == 3


async def test_calculator_happy_paths() -> None:
    assert (await calculator.invoke({"expression": "(1299 * 0.85) - 50"})).output["result"] == 1054.15
    assert (await calculator.invoke({"expression": "2 ^ 10"})).output["result"] == 1024
    assert (await calculator.invoke({"expression": "sqrt(16) + pi - pi"})).output["result"] == 4


@pytest.mark.parametrize(
    "expr,fragment",
    [
        ("__import__('os').system('ls')", "unsupported"),
        ("1/0", "division by zero"),
        ("2 ** 99999", "exponent too large"),
        ("factorial(10000)", "too large"),
        ("1 +", "invalid expression"),
        ("x" * 501, "too long"),
    ],
)
async def test_calculator_rejects_unsafe_or_invalid(expr: str, fragment: str) -> None:
    result = await calculator.invoke({"expression": expr})
    assert not result.success
    assert fragment in (result.error or "")


async def test_current_time() -> None:
    ok = await current_time.invoke({"timezone": "Asia/Shanghai"})
    assert ok.success and ok.output["iso"].endswith("+08:00")
    bad = await current_time.invoke({"timezone": "Mars/Base"})
    assert not bad.success and "unknown timezone" in (bad.error or "")


async def test_load_skill_tool(tmp_path: Path) -> None:
    (tmp_path / "pricing.md").write_text(
        "---\nname: pricing\ndescription: Price things\nversion: 1.2.0\n---\n# Steps\n1. Check costs",
        encoding="utf-8",
    )
    registry = SkillRegistry()
    registry.register_directory(tmp_path)
    load_skill = make_load_skill_tool(registry)
    ok = await load_skill.invoke({"skill": "pricing"})
    assert ok.output.startswith("# Skill: pricing (v1.2.0)")
    assert "1. Check costs" in ok.output
    missing = await load_skill.invoke({"skill": "nope"})
    assert not missing.success and "available: pricing" in (missing.error or "")
