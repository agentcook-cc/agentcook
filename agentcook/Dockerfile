# AgentCook agent runtime (FastAPI). Build from the repository root — the
# runtime depends on the agentcook-core / -providers / -storage workspace
# packages:
#
#   docker build -f agentcook/Dockerfile -t agentcook-runtime .
#   docker run -p 8000:8000 -e AGENTCOOK_JWT_SECRET=... agentcook-runtime
#
# Without a model API key the runtime answers with its offline mock model.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first (cached until the lockfile changes)…
COPY pyproject.toml uv.lock ./
COPY agentcook-core/pyproject.toml agentcook-core/
COPY agentcook-providers/pyproject.toml agentcook-providers/
COPY agentcook-storage/pyproject.toml agentcook-storage/
COPY agentcook/pyproject.toml agentcook/
COPY agentcook-swarm/pyproject.toml agentcook-swarm/
RUN mkdir -p agentcook-core/src/agentcook_core agentcook-providers/src/agentcook_providers \
        agentcook-storage/src/agentcook_storage agentcook/src/agentcook_app agentcook-swarm/src/agentcook_swarm \
    && uv sync --frozen --no-dev --no-install-workspace --package agentcook --extra postgres --extra providers

# …then the code.
COPY agentcook-core/src agentcook-core/src
COPY agentcook-providers/src agentcook-providers/src
COPY agentcook-storage/src agentcook-storage/src
COPY agentcook/src agentcook/src
RUN uv sync --frozen --no-dev --no-editable --package agentcook --extra postgres --extra providers

FROM python:3.12-slim
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    AGENTCOOK_ENV=production AGENTCOOK_AUTH_MODE=required
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# Migrations ship with the image. Production doesn't auto-migrate: run
# `alembic -c /app/agentcook/alembic.ini upgrade head` as a deploy step, or
# set AGENTCOOK_DB_AUTO_MIGRATE=true for single-replica setups.
COPY agentcook/alembic /app/agentcook/alembic
COPY agentcook/alembic.ini /app/agentcook/alembic.ini

RUN useradd --create-home --uid 10001 agentcook
USER agentcook
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "agentcook_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
