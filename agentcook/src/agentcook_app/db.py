"""Database migrations — run alembic programmatically.

Alembic remains the single source of truth for the runtime schema
(``agentcook/alembic/versions``). In development the app upgrades to
``head`` on startup (``AGENTCOOK_DB_AUTO_MIGRATE``, default on outside
production) so ``make dev`` against a fresh Postgres just works; in
production run ``uv run alembic upgrade head`` as a deploy step instead.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def alembic_dir() -> Path | None:
    """Locate the alembic script directory (repo checkout or container image)."""
    candidates = [
        os.environ.get("AGENTCOOK_ALEMBIC_DIR"),
        str(Path(__file__).resolve().parents[2] / "alembic"),  # agentcook/alembic in the repo
        "/app/agentcook/alembic",
        "/app/alembic",
    ]
    for candidate in candidates:
        if candidate and (Path(candidate) / "env.py").is_file():
            return Path(candidate)
    return None


def run_migrations(dsn: str) -> None:
    """``alembic upgrade head`` against *dsn* (blocking; call via to_thread)."""
    from alembic import command
    from alembic.config import Config

    script_dir = alembic_dir()
    if script_dir is None:
        logger.warning("alembic directory not found — skipping auto-migration")
        return
    config = Config()  # no ini file → alembic won't reconfigure app logging
    config.set_main_option("script_location", str(script_dir))
    config.attributes["url"] = dsn
    command.upgrade(config, "head")
    logger.info("database migrated to head (%s)", script_dir)


__all__ = ["alembic_dir", "run_migrations"]
