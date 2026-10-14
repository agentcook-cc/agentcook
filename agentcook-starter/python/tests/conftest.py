import asyncio
import json
import os

# Tests never depend on a developer's .env (e.g. MOCK_MODE=false + a real key).
os.environ.setdefault("MOCK_MODE", "true")

import pytest

import app.main  # noqa: F401  (registers the built-in tools, exactly as the server does)
from app.agent import core
from app.agent.context import SessionStore
from app.agent.mock_llm import MockLLM
from app.config import settings
from app.tools.registry import tool_registry


def collect(agen) -> list[dict]:
    """Drain run_agent() into a list of decoded events."""

    async def drain():
        return [json.loads(event) async for event in agen]

    return asyncio.run(drain())


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    """Each test gets empty sessions, an instant mock model and an untouched tool registry."""
    monkeypatch.setattr(settings, "mock_mode", True)
    monkeypatch.setattr(core, "sessions", SessionStore(max_messages=settings.max_context_messages))
    monkeypatch.setattr(core, "_llm", MockLLM(delay=0))
    monkeypatch.setattr(core, "_model", None)
    tools = dict(tool_registry._tools)
    yield
    tool_registry._tools.clear()
    tool_registry._tools.update(tools)
