"""Application container — every long-lived service, built once.

``create_app`` builds a :class:`AppContainer` synchronously (so a bare
``TestClient(app)`` works without running the lifespan) and the FastAPI
lifespan calls :meth:`AppContainer.start` / :meth:`AppContainer.stop`
for anything that needs I/O: connecting to Postgres, running migrations,
cancelling in-flight agent runs on shutdown.

Routers reach services through ``request.app.state.container`` (wrapped
in small ``Depends`` helpers), never through module-level singletons.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from agentcook_core import LLMProviderProtocol
from agentcook_core.conversations import ConversationStoreProtocol, InMemoryConversationStore
from agentcook_core.skill_loader import SkillLoadError, SkillRegistry, load_skill_file
from fastapi import Request

from agentcook_app.agents import AgentCatalog, load_agent_specs
from agentcook_app.config import Settings
from agentcook_app.log_stream import LogHub, get_log_hub
from agentcook_app.runs import DelegationLog, RunManager
from agentcook_app.services import AgentRuntime, InMemoryAgentRuntime
from agentcook_app.toolkits import ToolkitRegistry, builtin_toolkits

logger = logging.getLogger(__name__)


class StorageNotReadyError(RuntimeError):
    """Postgres storage is configured but the app has not started yet."""


def _load_skills(dirs: tuple[Path, ...]) -> SkillRegistry:
    registry = SkillRegistry()
    for directory in dirs:
        if not directory.is_dir():
            logger.warning("Skill directory %s does not exist — skipped", directory)
            continue
        for path in sorted(directory.rglob("*.md")):
            if path.name.startswith(("_", ".")) or path.name.lower() == "readme.md":
                continue
            try:
                entry = load_skill_file(path)
            except SkillLoadError as exc:
                logger.warning("Skipping skill %s: %s", path, exc)
                continue
            # Later directories override bundled skills of the same name.
            registry.register(entry, replace=True)
    return registry


class AppContainer:
    def __init__(
        self,
        settings: Settings,
        *,
        provider: LLMProviderProtocol | None = None,
        runtime: AgentRuntime | None = None,
        conversations: ConversationStoreProtocol | None = None,
        log_hub: LogHub | None = None,
    ) -> None:
        self.settings = settings
        self.log_hub = log_hub or get_log_hub()
        self.toolkits: ToolkitRegistry = builtin_toolkits()
        self.skills: SkillRegistry = _load_skills(settings.skills_dirs)
        self.agents = AgentCatalog(
            load_agent_specs(settings.agents_dir), default=settings.default_agent
        )
        self.agents.validate_toolkits(t.id for t in self.toolkits.list())
        self.runs = RunManager()
        self.delegations = DelegationLog()

        self._provider_override = provider
        self._providers: dict[str, LLMProviderProtocol] = {}
        self._pg_store: Any = None
        self._started = False

        use_postgres = settings.storage == "postgres"
        self._runtime: AgentRuntime | None = runtime or (
            None if use_postgres else InMemoryAgentRuntime()
        )
        self._conversations: ConversationStoreProtocol | None = conversations or (
            None if use_postgres else InMemoryConversationStore()
        )

    # -- storage ---------------------------------------------------------

    @property
    def runtime(self) -> AgentRuntime:
        if self._runtime is None:
            raise StorageNotReadyError("agent runtime not initialised (app not started)")
        return self._runtime

    @property
    def conversations(self) -> ConversationStoreProtocol:
        if self._conversations is None:
            raise StorageNotReadyError("conversation store not initialised (app not started)")
        return self._conversations

    # -- providers -------------------------------------------------------

    def provider_for(self, spec: str | None = None) -> LLMProviderProtocol:
        """Provider (or fallback chain) for *spec*, cached per spec string.

        ``None`` means the configured default (``AGENTCOOK_LLM_PROVIDER``).
        """
        if self._provider_override is not None:
            return self._provider_override
        key = (spec or self.settings.llm_provider).replace(" ", "")
        provider = self._providers.get(key)
        if provider is None:
            from agentcook_providers import create_provider_chain

            provider = create_provider_chain(key, delay_ms=self.settings.mock_delay_ms)
            self._providers[key] = provider
        return provider

    # -- lifecycle -------------------------------------------------------

    async def start(self) -> None:
        if self._started:
            return
        self.log_hub.bind_loop(asyncio.get_running_loop())
        if self.settings.storage == "postgres" and (
            self._runtime is None or self._conversations is None
        ):
            await self._start_postgres()
        self._started = True
        try:
            self.provider_for(None)
        except Exception as exc:
            logger.error(
                "default model %r is not usable: %s — chat requests will fail with "
                "MODEL_UNAVAILABLE until this is fixed",
                self.settings.llm_provider,
                exc,
            )
        logger.info(
            "agentcook runtime started (env=%s, provider=%s, storage=%s, auth=%s, agents=%s)",
            self.settings.env,
            self.settings.llm_provider,
            self.settings.storage,
            self.settings.auth_mode,
            ",".join(a.name for a in self.agents.list()),
        )

    async def _start_postgres(self) -> None:
        from agentcook_storage import HashingEmbedder, PgConversationStore, PostgresStore

        from agentcook_app.db import run_migrations
        from agentcook_app.runtime_pg import PgAgentRuntime

        dsn = self.settings.database_url
        assert dsn is not None
        if self.settings.db_auto_migrate:
            await asyncio.to_thread(run_migrations, dsn)
        store = await PostgresStore.connect(_asyncpg_dsn(dsn), min_size=1, max_size=10)
        self._pg_store = store
        if self._runtime is None:
            self._runtime = PgAgentRuntime(store, HashingEmbedder(1536), vector_dim=1536)
        if self._conversations is None:
            self._conversations = PgConversationStore(store)

    async def stop(self) -> None:
        await self.runs.shutdown()
        if self._pg_store is not None:
            await self._pg_store.close()
            self._pg_store = None
        self._started = False

    def describe(self) -> dict[str, Any]:
        return {
            "version": self.settings.version,
            "env": self.settings.env,
            "provider": self.settings.llm_provider,
            "mock_model": self.settings.uses_mock_model,
            "storage": self.settings.storage,
            "auth_mode": self.settings.auth_mode,
            "agents": [a.name for a in self.agents.list()],
            "default_agent": self.agents.default,
            "toolkits": [t.id for t in self.toolkits.list()],
            "skills": len(self.skills),
        }


def _asyncpg_dsn(dsn: str) -> str:
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres://"):
        if dsn.startswith(prefix):
            return "postgresql://" + dsn.removeprefix(prefix)
    return dsn


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


__all__ = ["AppContainer", "StorageNotReadyError", "get_container"]
