"""Alembic environment — uses raw SQL migrations (no SQLAlchemy ORM models).

Migration files under ``versions/`` execute plain ``op.execute(SQL)``
because the Python runtime accesses the DB through asyncpg directly
(see ``agentcook-storage/postgres.py``); we don't have ORM models to
auto-generate from.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_url() -> str:
    """Env-var override wins; else fall back to alembic.ini."""
    return os.environ.get("AGENTCOOK_DB_URL") or config.get_main_option(
        "sqlalchemy.url"
    )


def run_migrations_offline() -> None:
    context.configure(url=_resolve_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _resolve_url()
    # Alembic's sync engine only — DDL runs once at deploy time, not in the
    # hot request path, so the synchronous psycopg driver is fine here.
    # We rewrite asyncpg-style URLs to psycopg for alembic.
    if "+asyncpg" in section["sqlalchemy.url"]:
        section["sqlalchemy.url"] = section["sqlalchemy.url"].replace(
            "+asyncpg", "+psycopg"
        )

    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
