"""agentcook FastAPI runtime — Agent / Memory API.

Per ADR-013, this Python service is the Agent **runtime**; the business
backend (User / Permission / Connector / Audit Log) lives in
agentcook-java.
"""

from __future__ import annotations

from agentcook_app.main import app, create_app

__version__ = "0.1.0"

__all__ = ["__version__", "app", "create_app"]
