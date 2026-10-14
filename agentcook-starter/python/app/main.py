"""FastAPI entry point: register routes, mount the UI, set up CORS. Nothing else."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import VERSION, settings
from app.routers import chat, health

# --- Tools: importing a tool module registers it with tool_registry. --------
# Add a tool = create app/tools/<name>.py + add it to this import.
from app.tools import data_query, mock_search  # noqa: F401

logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="AgentCook Starter", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router)  # GET  /health
app.include_router(chat.router)  # POST /api/chat, GET /api/tools, DELETE /api/sessions/{id}
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")  # the chat UI
