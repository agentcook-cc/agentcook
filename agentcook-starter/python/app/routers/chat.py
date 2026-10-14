"""HTTP → agent → SSE. Protocol conversion only; no business logic here."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent.core import run_agent, sessions
from app.agent.guard import REFUSAL, check_injection
from app.config import settings
from app.models.schemas import ChatRequest, ToolInfo
from app.tools.registry import tool_registry

router = APIRouter(prefix="/api")


@router.post("/chat", response_class=StreamingResponse)
async def chat(request: ChatRequest):
    allowed = settings.allowed_user_set
    if allowed and request.user_id not in allowed:  # chapter 25: closed beta
        return JSONResponse(status_code=403, content={"message": "产品内测中，暂未开放。留下邮箱我们通知你 :)"})

    if settings.enable_input_guard and check_injection(request.message):
        events = _refusal()
    else:
        events = run_agent(request.message, request.session_id, user_id=request.user_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        async for event in events:
            yield f"data: {event}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    return [ToolInfo(name=t.name, description=t.description) for t in tool_registry.all()]


@router.delete("/sessions/{session_id}", status_code=204)
async def clear_session(session_id: str) -> None:
    sessions.delete(session_id)


async def _refusal() -> AsyncGenerator[str, None]:
    yield json.dumps({"type": "text", "content": REFUSAL}, ensure_ascii=False)
    yield json.dumps({"type": "done", "rounds": 0, "stop_reason": "refused", "usage": None})
