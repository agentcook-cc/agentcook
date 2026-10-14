"""agentcook FastAPI runtime — agent loop, conversations, skills, memory.

Per ADR-013, this Python service is the Agent **runtime**; the business
backend (users, permissions, plugin catalog, audit log) lives in
agentcook-java.

Importing this package is side-effect free; the ASGI app is built by
``agentcook_app.main`` (``uvicorn agentcook_app.main:app``) or
``agentcook_app.create_app()``.
"""

from __future__ import annotations

from typing import Any

__version__ = "2.0.0"


def create_app(*args: Any, **kwargs: Any) -> Any:
    from agentcook_app.main import create_app as _create_app

    return _create_app(*args, **kwargs)


def __getattr__(name: str) -> Any:
    if name == "app":
        from agentcook_app.main import app

        return app
    raise AttributeError(name)


__all__ = ["__version__", "create_app"]
