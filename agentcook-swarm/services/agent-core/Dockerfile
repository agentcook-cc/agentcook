# agent-core for the swarm topology: the AgentCook runtime (HTTP :8000) plus
# its gRPC ChatService (:50051) and etcd self-registration. Build from the
# repository root:
#
#   docker build -f agentcook-swarm/services/agent-core/Dockerfile -t agentcook-agent-core .

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY agentcook-core/pyproject.toml agentcook-core/
COPY agentcook-providers/pyproject.toml agentcook-providers/
COPY agentcook-storage/pyproject.toml agentcook-storage/
COPY agentcook/pyproject.toml agentcook/
COPY agentcook-swarm/pyproject.toml agentcook-swarm/
RUN mkdir -p agentcook-core/src/agentcook_core agentcook-providers/src/agentcook_providers \
        agentcook-storage/src/agentcook_storage agentcook/src/agentcook_app agentcook-swarm/src/agentcook_swarm \
    && uv sync --frozen --no-dev --no-install-workspace --package agentcook --extra postgres --extra providers --extra otel

COPY agentcook-core/src agentcook-core/src
COPY agentcook-providers/src agentcook-providers/src
COPY agentcook-storage/src agentcook-storage/src
COPY agentcook/src agentcook/src
RUN uv sync --frozen --no-dev --no-editable --package agentcook --extra postgres --extra providers --extra otel

# Swarm-only extras (gRPC server, health/reflection, etcd, structlog) and the
# generated stubs from the one canonical proto.
COPY agentcook-swarm/services/agent-core/requirements.txt /tmp/requirements.txt
COPY proto/ /app/proto/
RUN uv pip install --python /app/.venv/bin/python -r /tmp/requirements.txt \
    && mkdir /stubs \
    && /app/.venv/bin/python -m grpc_tools.protoc -I /app/proto --python_out=/stubs --grpc_python_out=/stubs /app/proto/agentcook.proto

FROM python:3.12-slim
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    AGENT_CORE_PORT=8000 GRPC_PORT=50051
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /stubs/ /app/
COPY agentcook/alembic /app/agentcook/alembic
COPY agentcook/alembic.ini /app/agentcook/alembic.ini
COPY agentcook-swarm/services/agent-core/*.py /app/

RUN useradd --create-home --uid 10001 agentcook
USER agentcook
EXPOSE 8000 50051
CMD ["python", "main.py"]
