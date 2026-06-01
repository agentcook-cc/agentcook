"""gRPC server for agent-core ChatService.

Implements ChatService.StreamChat by bridging to the existing
FastAPI chat/stream logic, converting SSE frames to gRPC ChatFrame messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
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

    Bridges incoming gRPC StreamChat requests to the internal chat logic,
    producing a stream of ChatFrame messages.
    """

    def __init__(self) -> None:
        self._request_count = 0

    async def StreamChat(self, request, context):
        """Handle streaming chat request.

        Bridges gRPC ChatRequest to the internal _stream_mock_response generator,
        parsing SSE bytes into gRPC ChatFrame messages.
        """
        import agentcook_pb2 as pb2

        self._request_count += 1
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        logger.info(
            "gRPC StreamChat: session=%s, model=%s, plugins=%s",
            request.session_id,
            request.model or "default",
            list(request.plugin_ids),
        )

        try:
            from agentcook_app.routers.chat import _stream_mock_response
            from agentcook_app.schemas_chat import ChatStreamRequest

            # Build the ChatStreamRequest that _stream_mock_response expects
            chat_request = ChatStreamRequest(
                session_id=request.session_id,
                message=request.message,
                plugin_ids=list(request.plugin_ids) if request.plugin_ids else None,
                model=request.model or None,
                temperature=request.temperature if request.temperature else None,
                max_tokens=request.max_tokens if request.max_tokens else None,
            )

            async for sse_bytes in _stream_mock_response(chat_request):
                # Each yield is bytes: b"data: {json}\n\n"
                sse_line = sse_bytes.decode("utf-8").strip() if isinstance(sse_bytes, bytes) else str(sse_bytes).strip()
                frame_data = _parse_sse_frame(sse_line)
                if not frame_data:
                    continue

                metadata = None
                if frame_data.get("done") and "metadata" in frame_data:
                    meta = frame_data["metadata"]
                    usage = meta.get("usage", {})
                    metadata = pb2.ChatMetadata(
                        model=meta.get("model", ""),
                        prompt_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                        completion_tokens=usage.get("output_tokens", usage.get("completion_tokens", 0)),
                        request_id=meta.get("request_id", request_id),
                        duration_ms=int((time.monotonic() - start_time) * 1000),
                    )

                frame = pb2.ChatFrame(
                    role=frame_data.get("role", "assistant"),
                    content=frame_data.get("content", ""),
                    done=frame_data.get("done", False),
                    metadata=metadata,
                )
                yield frame

        except Exception as exc:
            logger.error("StreamChat error: %s", exc)
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))


async def serve_grpc(port: int = 50051) -> None:
    """Start the async gRPC server with health check and reflection."""
    if not _GRPC_AVAILABLE:
        logger.warning("grpcio not installed, gRPC server disabled")
        return

    import agentcook_pb2_grpc as pb2_grpc
    import agentcook_pb2 as pb2

    server = grpc.aio.server()

    # Register ChatService
    chat_servicer = ChatServiceServicer()
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
