"""Runtime configuration — one typed object instead of scattered ``os.environ``.

Every setting is read once, validated, and documented here. Modules take
a :class:`Settings` (usually via ``app.state.container.settings``) rather
than reading the environment themselves, which keeps behaviour
predictable in tests and makes the full configuration surface
discoverable in one place.

Environment variables (all optional):

=================================  ==========================================================
``AGENTCOOK_ENV``                  ``development`` (default) / ``test`` / ``production``
``AGENTCOOK_LOG_LEVEL``            ``INFO``
``AGENTCOOK_CORS_ORIGINS``         comma list; defaults to the local admin/app dev servers
``AGENTCOOK_LLM_PROVIDER``         ``qwen`` / ``openai`` / ``anthropic`` / ``zhipu`` / ``mock``;
                                   may be a fallback chain: ``qwen:qwen-plus,zhipu,mock``
``AGENTCOOK_LLM_FALLBACKS``        extra providers appended to the chain (comma list)
``AGENTCOOK_CHAT_MOCK``            ``true`` forces the offline mock model (legacy flag)
``AGENTCOOK_MOCK_DELAY_MS``        per-chunk delay of the mock model (UX realism; 0 in tests)
``AGENTCOOK_AUTH_MODE``            ``required`` / ``optional`` / ``disabled``
                                   (default: ``required`` in production, else ``optional``)
``AGENTCOOK_JWT_SECRET``           HS256 secret shared with agentcook-java
                                   (``AGENTCOOK_AUTH_JWT_SECRET`` accepted — Java's name)
``AGENTCOOK_JWT_PUBLIC_KEY``       PEM public key (switches verification to RS256)
``AGENTCOOK_JWT_ALG``              override the algorithm
``AGENTCOOK_JWT_ISSUER``           if set, the ``iss`` claim must match
``AGENTCOOK_DATABASE_URL``         Postgres DSN → durable transcripts + memory
``AGENTCOOK_STORAGE``              ``memory`` / ``postgres`` (default: postgres iff DSN set)
``AGENTCOOK_DB_AUTO_MIGRATE``      run alembic on startup (default: on outside production)
``AGENTCOOK_REDIS_URL``            only used by the readiness probe when set
``AGENTCOOK_SKILLS_DIRS``          extra skill directories (``os.pathsep``-separated)
``AGENTCOOK_AGENTS_DIR``           directory of agent spec YAML/JSON files (overrides bundled)
``AGENTCOOK_DEFAULT_AGENT``        agent used when a request names none (``assistant``)
``AGENTCOOK_DISABLED_TOOLS``       comma list of tool names no agent may call
``AGENTCOOK_MAX_TURNS``            default agent turn budget (8)
``AGENTCOOK_TOOL_TIMEOUT``         default per-tool timeout seconds (30)
``AGENTCOOK_HISTORY_LIMIT``        transcript messages replayed per turn (200)
``AGENTCOOK_QUOTA_ENABLED``        enable ADR-018 quota routing via agentcook-java
``AGENTCOOK_JAVA_BASE_URL``        agentcook-java base URL (quota lookups / consumption)
``AGENTCOOK_TURNSTILE_ENFORCE``    require Cloudflare Turnstile tokens on chat
``OTEL_EXPORTER_OTLP_ENDPOINT``    enables tracing export when set
=================================  ==========================================================
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Environment = Literal["development", "test", "production"]
AuthMode = Literal["required", "optional", "disabled"]
StorageBackend = Literal["memory", "postgres"]

# Same default as agentcook-java's application.yml so a token issued by
# the Java login in local dev verifies here without extra configuration.
DEV_JWT_SECRET = "phase3-dev-secret-not-for-prod-32bytes!!"

DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",  # admin (Vue) dev server
    "http://localhost:5174",  # app (React) dev server
    "http://localhost:3000",  # docs / generic dev
)
RUNTIME_VERSION = "2.0.0"

PACKAGE_DIR = Path(__file__).resolve().parent
BUNDLED_SKILLS_DIR = PACKAGE_DIR / "skills"
BUNDLED_AGENTS_DIR = PACKAGE_DIR / "agents"


class ConfigError(ValueError):
    """Invalid or unsafe configuration."""


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    env: Environment = "development"
    log_level: str = "INFO"
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS

    llm_provider: str = "mock"
    mock_delay_ms: float = 0.0

    auth_mode: AuthMode = "optional"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_public_key: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_issuer: str | None = None

    storage: StorageBackend = "memory"
    database_url: str | None = None
    db_auto_migrate: bool = True
    redis_url: str | None = None

    skills_dirs: tuple[Path, ...] = (BUNDLED_SKILLS_DIR,)
    agents_dir: Path = BUNDLED_AGENTS_DIR
    default_agent: str = "assistant"
    disabled_tools: tuple[str, ...] = ()
    max_turns: int = 8
    tool_timeout: float = 30.0
    history_limit: int = 200

    quota_enabled: bool = False
    java_base_url: str = "http://localhost:8080"
    turnstile_enforce: bool = False

    otel_endpoint: str | None = None
    version: str = RUNTIME_VERSION
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def uses_mock_model(self) -> bool:
        return self.llm_provider.split(",")[0].split(":")[0].strip() in ("mock", "echo")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if environ is None else environ
        env_raw = (e.get("AGENTCOOK_ENV") or "development").strip().lower()
        aliases = {"dev": "development", "local": "development", "prod": "production"}
        env_name = aliases.get(env_raw, env_raw)
        if env_name not in ("development", "test", "production"):
            raise ConfigError(f"AGENTCOOK_ENV must be development/test/production, got {env_raw!r}")

        provider = (e.get("AGENTCOOK_LLM_PROVIDER") or "").strip()
        if _truthy(e.get("AGENTCOOK_CHAT_MOCK")) or not provider:
            provider = "mock"
        fallbacks = _csv(e.get("AGENTCOOK_LLM_FALLBACKS"))
        if fallbacks:
            provider = ",".join((provider, *fallbacks))

        auth_mode = (e.get("AGENTCOOK_AUTH_MODE") or "").strip().lower() or (
            "required" if env_name == "production" else "optional"
        )
        if auth_mode not in ("required", "optional", "disabled"):
            raise ConfigError(
                f"AGENTCOOK_AUTH_MODE must be required/optional/disabled, got {auth_mode!r}"
            )

        public_key = e.get("AGENTCOOK_JWT_PUBLIC_KEY") or None
        secret = (
            e.get("AGENTCOOK_JWT_SECRET") or e.get("AGENTCOOK_AUTH_JWT_SECRET") or DEV_JWT_SECRET
        )
        algorithm = e.get("AGENTCOOK_JWT_ALG") or ("RS256" if public_key else "HS256")

        database_url = e.get("AGENTCOOK_DATABASE_URL") or None
        storage = (e.get("AGENTCOOK_STORAGE") or ("postgres" if database_url else "memory")).lower()
        if storage not in ("memory", "postgres"):
            raise ConfigError(f"AGENTCOOK_STORAGE must be memory/postgres, got {storage!r}")
        if storage == "postgres" and not database_url:
            raise ConfigError("AGENTCOOK_STORAGE=postgres requires AGENTCOOK_DATABASE_URL")

        skills_dirs: list[Path] = [BUNDLED_SKILLS_DIR]
        for raw in (e.get("AGENTCOOK_SKILLS_DIRS") or "").split(os.pathsep):
            if raw.strip():
                skills_dirs.append(Path(raw.strip()).expanduser())

        settings = cls(
            env=env_name,  # type: ignore[arg-type]
            log_level=(e.get("AGENTCOOK_LOG_LEVEL") or "INFO").upper(),
            cors_origins=_csv(e.get("AGENTCOOK_CORS_ORIGINS")) or DEFAULT_CORS_ORIGINS,
            llm_provider=provider,
            mock_delay_ms=float(e.get("AGENTCOOK_MOCK_DELAY_MS") or 0),
            auth_mode=auth_mode,  # type: ignore[arg-type]
            jwt_secret=secret,
            jwt_public_key=public_key,
            jwt_algorithm=algorithm,
            jwt_issuer=e.get("AGENTCOOK_JWT_ISSUER") or None,
            storage=storage,  # type: ignore[arg-type]
            database_url=database_url,
            db_auto_migrate=_truthy(
                e.get("AGENTCOOK_DB_AUTO_MIGRATE"), default=env_name != "production"
            ),
            redis_url=e.get("AGENTCOOK_REDIS_URL") or None,
            skills_dirs=tuple(skills_dirs),
            agents_dir=Path(e["AGENTCOOK_AGENTS_DIR"]).expanduser()
            if e.get("AGENTCOOK_AGENTS_DIR")
            else BUNDLED_AGENTS_DIR,
            default_agent=e.get("AGENTCOOK_DEFAULT_AGENT") or "assistant",
            disabled_tools=_csv(e.get("AGENTCOOK_DISABLED_TOOLS")),
            max_turns=int(e.get("AGENTCOOK_MAX_TURNS") or 8),
            tool_timeout=float(e.get("AGENTCOOK_TOOL_TIMEOUT") or 30),
            history_limit=int(e.get("AGENTCOOK_HISTORY_LIMIT") or 200),
            quota_enabled=_truthy(e.get("AGENTCOOK_QUOTA_ENABLED")),
            java_base_url=(e.get("AGENTCOOK_JAVA_BASE_URL") or "http://localhost:8080").rstrip("/"),
            turnstile_enforce=_truthy(e.get("AGENTCOOK_TURNSTILE_ENFORCE")),
            otel_endpoint=e.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None,
            version=e.get("AGENTCOOK_VERSION") or RUNTIME_VERSION,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Refuse configurations that are unsafe to run in production."""
        if self.max_turns < 1:
            raise ConfigError("AGENTCOOK_MAX_TURNS must be >= 1")
        if self.tool_timeout <= 0:
            raise ConfigError("AGENTCOOK_TOOL_TIMEOUT must be > 0")
        if not self.is_production:
            return
        if self.auth_mode != "required":
            raise ConfigError("production requires AGENTCOOK_AUTH_MODE=required")
        if not self.jwt_public_key and self.jwt_secret == DEV_JWT_SECRET:
            raise ConfigError(
                "production requires AGENTCOOK_JWT_SECRET (or AGENTCOOK_JWT_PUBLIC_KEY); "
                "refusing to start with the public development secret"
            )
        if not self.jwt_public_key and len(self.jwt_secret.encode()) < 32:
            raise ConfigError("AGENTCOOK_JWT_SECRET must be at least 32 bytes (HS256)")


__all__ = [
    "BUNDLED_AGENTS_DIR",
    "BUNDLED_SKILLS_DIR",
    "DEFAULT_CORS_ORIGINS",
    "DEV_JWT_SECRET",
    "RUNTIME_VERSION",
    "AuthMode",
    "ConfigError",
    "Environment",
    "Settings",
]
