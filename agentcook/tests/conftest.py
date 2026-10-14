"""Shared fixtures for the agentcook runtime tests.

``make_app`` builds a fully isolated application (own container, own
in-memory stores) with optional overrides, so tests never share state
through module-level singletons.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from agentcook_app.config import Settings
from agentcook_app.container import AppContainer
from agentcook_app.main import create_app
from fastapi.testclient import TestClient

TEST_SECRET = "test-secret-do-not-use-anywhere-else-32b"


def make_settings(**overrides: Any) -> Settings:
    base = Settings.from_env({"AGENTCOOK_JWT_SECRET": TEST_SECRET})
    return dataclasses.replace(base, **overrides)


def make_token(
    sub: str = "user-1",
    *,
    scopes: str = "agent:read agent:write",
    minutes: int = 15,
    secret: str = TEST_SECRET,
    **claims: Any,
) -> str:
    payload = {
        "sub": sub,
        "scopes": scopes,
        "exp": dt.datetime.now(tz=dt.UTC) + dt.timedelta(minutes=minutes),
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def auth(sub: str = "user-1", **kw: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub, **kw)}"}


def sse_frames(text: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def make_app() -> Callable[..., Any]:
    def _make(*, provider: Any = None, **overrides: Any) -> Any:
        settings = make_settings(**overrides)
        container = AppContainer(settings, provider=provider)
        return create_app(settings, container=container)

    return _make


@pytest.fixture
def client(make_app: Callable[..., Any]) -> Iterator[TestClient]:
    with TestClient(make_app()) as c:
        yield c


@pytest.fixture(name="auth")
def auth_fixture() -> Callable[..., dict[str, str]]:
    """``auth("alice")`` → Authorization header for a valid token."""
    return auth


@pytest.fixture(name="token")
def token_fixture() -> Callable[..., str]:
    return make_token


@pytest.fixture(name="sse")
def sse_fixture() -> Callable[[str], list[dict[str, Any]]]:
    """Parse an SSE body into its JSON ``data:`` frames."""
    return sse_frames
