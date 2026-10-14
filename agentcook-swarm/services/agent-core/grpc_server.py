"""gRPC server for agent-core ChatService.

Implements ChatService.StreamChat on top of the runtime's agent loop
(``agentcook_app.chat_service``) — the same code path as the HTTP SSE
endpoint — and converts its frames to gRPC ChatFrame messages.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# gRPC imports (available when grpcio is installed)
try:
    import grpc
    from grpc_health.v1 import health, health_pb2, health_pb2_grpc
    from grpc_reflection.v1alpha import reflection

    _GRPC_AVAILABLE = True
except ImportError:
    _GRPC_AVAILABLE = False


def _parse_sse_frame(line: str) -> dict[str, Any] | None:
    """Parse a single SSE data line into a dict."""
    if not line.startswith("data: "):
        return None
    try:
        return json.loads(line[6:])
    except (json.JSONDecodeError, ValueError):
        return None


class ChatServiceServicer:
    """gRPC ChatService implementation.

    Runs the *same* agent loop as ``POST /api/v1/chat/stream`` (through
    :class:`agentcook_app.chat_service.ChatService` on the shared app
    container) and maps each frame onto a ``ChatFrame``. Callers forward
    the end user's JWT in the ``authorization`` metadata key; without it
    the call is anonymous unless the runtime requires auth.
    """

    def __init__(self, container: Any = None) -> None:
        self._request_count = 0
        self._container = container

    def _get_container(self) -> Any:
        if self._container is None:
            from agentcook_app.config import Settings
            from agentcook_app.container import AppContainer

            self._container = AppContainer(Settings.from_env())
        return self._container

    async def StreamChat(self, request, context):  # noqa: N802 — gRPC method name
        import agentcook_pb2 as pb2
        from agentcook_app.chat_service import ChatService, ChatTurn
        from agentcook_app.security import ANONYMOUS_USER_ID, UserContext, decode_token
        from fastapi import HTTPException

        self._request_count += 1
        container = self._get_container()
        settings = container.settings
        start_time = time.monotonic()

        metadata = dict(context.invocation_metadata() or ())
        token = str(metadata.get("authorization", "")).removeprefix("Bearer ").strip()
        try:
            if token:
                user = decode_token(token, settings)
            elif settings.auth_mode == "required":
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "missing bearer token")
                return
            else:
                user = UserContext(user_id=ANONYMOUS_USER_ID, scopes=frozenset(), anonymous=True)
        except HTTPException as exc:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc.detail))
            return

        logger.info(
            "gRPC StreamChat: session=%s model=%s plugins=%s user=%s",
            request.session_id,
            request.model or "default",
            list(request.plugin_ids),
            user.user_id,
        )
        turn = ChatTurn(
            session_id=request.session_id,
            message=request.message,
            plugin_ids=tuple(request.plugin_ids),
            model=request.model or None,
            temperature=request.temperature or None,
            max_tokens=request.max_tokens or None,
        )
        try:
            handle = await ChatService(container).start_turn(user, turn)
        except Exception as exc:  # noqa: BLE001 — map every setup failure to a status
            status = grpc.StatusCode.INVALID_ARGUMENT
            name = type(exc).__name__
            if name in ("SessionBusyError",):
                status = grpc.StatusCode.FAILED_PRECONDITION
            elif name in ("StorageNotReadyError", "ModelUnavailableError"):
                status = grpc.StatusCode.UNAVAILABLE
            elif name in ("AgentNotAvailableError", "SessionAccessError"):
                status = grpc.StatusCode.NOT_FOUND
            await context.abort(status, str(exc))
            return

        async for frame_data in handle.frames():
            if frame_data is None:
                continue  # heartbeat — gRPC keeps its own keepalive
            kind = frame_data.get("type")
            if kind in ("tool_call", "tool_result", "start"):
                continue  # ChatFrame v1 carries text only
            frame_metadata = None
            if frame_data.get("done"):
                meta = frame_data.get("metadata", {})
                usage = meta.get("usage", {})
                frame_metadata = pb2.ChatMetadata(
                    model=meta.get("model", ""),
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    request_id=meta.get("request_id", handle.run_id),
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
            content = frame_data.get("content", "")
            if kind == "error":
                content = frame_data.get("error", "") or content
            yield pb2.ChatFrame(
                role="assistant",
                content=content,
                done=bool(frame_data.get("done")),
                metadata=frame_metadata,
            )


async def serve_grpc(port: int = 50051, *, container: Any = None) -> None:
    """Start the async gRPC server with health check and reflection.

    Pass the HTTP app's container so both transports share one runtime
    (run manager, stores, provider cache).
    """
    if not _GRPC_AVAILABLE:
        logger.warning("grpcio not installed, gRPC server disabled")
        return

    import agentcook_pb2 as pb2
    import agentcook_pb2_grpc as pb2_grpc

    server = grpc.aio.server()

    # Register ChatService
    chat_servicer = ChatServiceServicer(container)
    pb2_grpc.add_ChatServiceServicer_to_server(chat_servicer, server)

    # Register health check
    health_servicer = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    await health_servicer.set(
        "cc.agentcook.grpc.ChatService",
        health_pb2.HealthCheckResponse.SERVING,
    )

    # Register reflection (for grpcurl / grpcui)
    service_names = (
        pb2.DESCRIPTOR.services_by_name["ChatService"].full_name,
        health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)
    logger.info("gRPC server starting on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()
