"""agent-core microservice entry point.

Starts both FastAPI (HTTP) and gRPC servers concurrently.
- HTTP: model_router + hook_runtime + sandbox_runner + compaction + media + chat/stream
- gRPC: ChatService.StreamChat
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

import uvicorn

# Replace basic stdlib config with structured JSON via structlog.
# Falls back to plain stdlib if structlog isn't installed (safe in tests).
try:
    from logging_config import configure_logging

    configure_logging()
except Exception:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-core")

HTTP_PORT = int(os.getenv("AGENT_CORE_PORT", "8000"))
GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))
ETCD_HOST = os.getenv("ETCD_HOST", "etcd")
ETCD_PORT = int(os.getenv("ETCD_PORT", "2379"))


async def start_grpc_server() -> None:
    """Start gRPC server in background."""
    # Enable OTel gRPC server instrumentation BEFORE the server is built so
    # the interceptor wraps it. Safe no-op if the package is missing.
    try:
        from observability import setup_grpc_server_instrumentation

        setup_grpc_server_instrumentation()
    except Exception as exc:  # noqa: BLE001
        logger.warning("gRPC server instrumentation skipped: %s", exc)

    try:
        from grpc_server import serve_grpc
        await serve_grpc(port=GRPC_PORT)
    except ImportError:
        logger.warning("gRPC server not available (grpcio not installed), skipping")
    except Exception as exc:
        logger.error("gRPC server failed: %s", exc)


async def register_with_etcd() -> None:
    """Register service with etcd for discovery."""
    try:
        from etcd_registry import EtcdServiceRegistry
        registry = EtcdServiceRegistry(host=ETCD_HOST, port=ETCD_PORT)
        instance_id = os.getenv("INSTANCE_ID", f"agent-core-{os.getpid()}")
        await registry.register(
            service_name="agent-core",
            instance_id=instance_id,
            host=os.getenv("ADVERTISE_HOST", "agent-core"),
            port=HTTP_PORT,
            metadata={"grpc_port": GRPC_PORT},
        )
        logger.info("Registered with etcd: agent-core/%s", instance_id)
    except ImportError:
        logger.warning("etcd registry not available, skipping registration")
    except Exception as exc:
        logger.warning("etcd registration failed (degraded mode): %s", exc)


def create_app():
    """Create the FastAPI application (imports from agentcook_app).

    OTel telemetry is wired here so every request flowing through the
    HTTP routes inherits the instrumentation. Failure to wire telemetry
    must never break app creation — observability is best-effort.
    """
    from agentcook_app.main import create_app as _create_app

    app = _create_app()
    try:
        from observability import setup_telemetry

        setup_telemetry(app)
    except Exception as exc:  # noqa: BLE001
        logger.warning("setup_telemetry failed (degraded): %s", exc)
    return app


async def main() -> None:
    """Run HTTP + gRPC servers concurrently."""
    logger.info("Starting agent-core: HTTP=%d, gRPC=%d", HTTP_PORT, GRPC_PORT)

    # Register with etcd (best-effort)
    await register_with_etcd()

    # Start gRPC in background
    grpc_task = asyncio.create_task(start_grpc_server())

    # Start HTTP (uvicorn)
    config = uvicorn.Config(
        app="main:create_app",
        factory=True,
        host="0.0.0.0",
        port=HTTP_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(server.shutdown()))

    await server.serve()
    grpc_task.cancel()
    logger.info("agent-core shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
