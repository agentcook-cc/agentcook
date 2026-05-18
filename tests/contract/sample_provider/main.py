"""Sample HTTP provider wrapping EchoProvider.

Why this exists:
    EchoProvider (agentcook_providers) is a *Python* protocol — no HTTP surface.
    Pact verifies HTTP/message contracts, so we need a thin FastAPI wrapper to
    serve as a sample provider for the Pact consumer/provider e2e.

    This is a TEACHING stub for tests/contract/. Day 22 Agent A swaps it
    for the real `agentcook` (FastAPI main shell). The 3 status-code shapes
    below (200 / 400 / 404) cover the cases the real API will eventually
    exercise too — the consumer contract test already pins that expectation.
"""

from __future__ import annotations

from agentcook_core import Message
from agentcook_providers import EchoProvider
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class EchoReply(BaseModel):
    reply: str
    model: str


class ErrorBody(BaseModel):
    error: str
    code: str


# Tiny in-memory profile store so the 404 case has something concrete to miss.
_PROFILES: dict[str, dict[str, str]] = {
    "alice": {"id": "alice", "display_name": "Alice"},
}


def create_app(prefix: str = "Echo") -> FastAPI:
    """Build the sample provider FastAPI app. Factory style to ease testing."""
    app = FastAPI(title="echo-api", version="0.1.0")
    provider = EchoProvider(prefix=prefix)

    @app.get("/v1/echo", response_model=EchoReply, responses={400: {"model": ErrorBody}})
    async def echo(text: str = Query(...)) -> EchoReply:
        # Reject empty text with a structured 400 (FastAPI default would 422
        # on missing param; we want a stable contract surface).
        if not text:
            return JSONResponse(
                status_code=400,
                content={"error": "text must not be empty", "code": "empty_text"},
            )
        resp = await provider.chat([Message(role="user", content=text)])
        return EchoReply(reply=resp.message.content, model=provider.model_name)

    @app.get(
        "/v1/profiles/{profile_id}",
        responses={200: {}, 404: {"model": ErrorBody}},
    )
    async def get_profile(profile_id: str):
        profile = _PROFILES.get(profile_id)
        if profile is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": f"profile {profile_id!r} not found",
                    "code": "profile_missing",
                },
            )
        return profile

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
