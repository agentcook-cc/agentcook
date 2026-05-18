"""Plugin loader: parse a Plugin Bundle directory into an in-memory
:class:`PluginEntry` satisfying :class:`PluginProtocol`.

A Plugin Bundle on disk follows the ``agent-plugin-spec`` layout::

    my-plugin/
      plugin.json          # manifest (name, version, description, …)
      agents/
        agent-a/
          agent.json       # AgentProtocol metadata
      skills/
        skill-x.md         # SkillProtocol markdown
      connectors/
        connectors.json    # ConnectorProtocol declarations

The loader validates the manifest, delegates skill loading to
:mod:`agentcook_core.skill_loader`, and prepares a sandbox-ready
handle when the plugin declares ``sandbox: true``.

Design decisions:
- **stdlib-only** for JSON parsing (no pydantic at the core layer).
- **Sandbox integration** is an optional callback — the core loader
  does not import Docker; callers inject a
  :class:`SandboxRunner` protocol if sandbox execution is needed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence, runtime_checkable

from agentcook_core.protocols import (
    AgentProtocol,
    ConnectorProtocol,
    PluginProtocol,
    SkillProtocol,
)
from agentcook_core.skill_loader import SkillEntry, load_skill_file, SkillLoadError
from agentcook_core.types import (
    ConnectorConfig,
    ConnectorKind,
    ModelSpec,
    PluginManifest,
    SkillManifest,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PluginLoadError(Exception):
    """Raised when a plugin bundle cannot be loaded."""


class PluginManifestError(PluginLoadError):
    """Raised when ``plugin.json`` is missing or invalid."""


# ---------------------------------------------------------------------------
# Sandbox runner protocol (injected, not owned)
# ---------------------------------------------------------------------------

@runtime_checkable
class SandboxRunner(Protocol):
    """Callback protocol for executing plugin scripts in a sandbox.

    Matches the shape of ``poc/plugin-sandbox/sandbox_runner.py``'s
    ``run_plugin_script`` function so it can be passed directly.
    """

    def __call__(
        self,
        plugin_dir: str,
        script_name: str,
        *,
        timeout: int = 30,
        cpu_limit: float = 0.5,
        memory_limit: str = "512m",
    ) -> Any: ...


# ---------------------------------------------------------------------------
# Stub implementations for agents / connectors parsed from JSON
# ---------------------------------------------------------------------------

@dataclass
class AgentStub:
    """Minimal :class:`AgentProtocol`-shaped stub loaded from ``agent.json``.

    The stub carries metadata only — actual LLM execution is wired by
    the runtime layer (``agentcook`` main shell), not the core loader.
    """

    _name: str
    _description: str
    _model: ModelSpec

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def model(self) -> ModelSpec:
        return self._model

    async def run(self, messages, *, context=None):  # type: ignore[override]
        raise NotImplementedError(
            f"AgentStub({self._name!r}).run() is metadata-only; "
            "wire a real provider via the runtime layer"
        )


@dataclass
class ConnectorStub:
    """Minimal :class:`ConnectorProtocol`-shaped stub from ``connectors.json``."""

    _config: ConnectorConfig

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    async def open(self) -> None:
        raise NotImplementedError("ConnectorStub.open() — wire via runtime")

    async def close(self) -> None:
        pass  # safe no-op

    async def tools(self):  # type: ignore[override]
        return ()


# ---------------------------------------------------------------------------
# PluginEntry — loaded plugin satisfying PluginProtocol
# ---------------------------------------------------------------------------

@dataclass
class PluginEntry:
    """Concrete :class:`PluginProtocol` implementation backed by a directory."""

    _manifest: PluginManifest
    _agents: list[AgentStub] = field(default_factory=list)
    _skills: list[SkillEntry] = field(default_factory=list)
    _connectors: list[ConnectorStub] = field(default_factory=list)
    _path: Path = field(default_factory=lambda: Path("."))
    _sandbox_runner: SandboxRunner | None = field(default=None, repr=False)
    _activated: bool = field(default=False, repr=False)

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    @property
    def agents(self) -> Sequence[AgentStub]:
        return self._agents

    @property
    def skills(self) -> Sequence[SkillEntry]:
        return self._skills

    @property
    def connectors(self) -> Sequence[ConnectorStub]:
        return self._connectors

    async def activate(self) -> None:
        if self._activated:
            return
        logger.info("Activating plugin %r", self._manifest.name)
        self._activated = True

    async def deactivate(self) -> None:
        if not self._activated:
            return
        logger.info("Deactivating plugin %r", self._manifest.name)
        self._activated = False

    @property
    def is_active(self) -> bool:
        return self._activated


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------

_REQUIRED_MANIFEST_FIELDS = ("name", "display_name", "version", "description")


def parse_manifest(manifest_path: Path) -> PluginManifest:
    """Read and validate ``plugin.json`` into a :class:`PluginManifest`."""
    if not manifest_path.exists():
        raise PluginManifestError(f"plugin.json not found: {manifest_path}")

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PluginManifestError(f"Invalid JSON in {manifest_path}: {exc}") from exc

    missing = [f for f in _REQUIRED_MANIFEST_FIELDS if f not in raw]
    if missing:
        raise PluginManifestError(
            f"plugin.json missing required fields: {missing} ({manifest_path})"
        )

    return PluginManifest(
        name=raw["name"],
        display_name=raw["display_name"],
        version=raw["version"],
        description=raw["description"],
        author=raw.get("author"),
        category=raw.get("category"),
        default_agent=raw.get("default_agent"),
    )


# ---------------------------------------------------------------------------
# Sub-loaders (agents / connectors from JSON)
# ---------------------------------------------------------------------------

def _load_agents(agents_dir: Path) -> list[AgentStub]:
    """Scan ``agents/`` subdirectories for ``agent.json`` files."""
    if not agents_dir.is_dir():
        return []

    agents: list[AgentStub] = []
    for child in sorted(agents_dir.iterdir()):
        agent_json = child / "agent.json" if child.is_dir() else None
        if agent_json is None or not agent_json.exists():
            continue
        try:
            raw = json.loads(agent_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping agent %s: %s", child.name, exc)
            continue

        model_raw = raw.get("model", {})
        agents.append(
            AgentStub(
                _name=raw.get("name", child.name),
                _description=raw.get("description", ""),
                _model=ModelSpec(
                    provider=model_raw.get("provider", "openai"),
                    name=model_raw.get("name", "gpt-4o"),
                ),
            )
        )
    return agents


def _load_connectors(connectors_path: Path) -> list[ConnectorStub]:
    """Parse ``connectors/connectors.json`` into stubs."""
    if not connectors_path.exists():
        return []

    try:
        raw = json.loads(connectors_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Skipping connectors: %s", exc)
        return []

    entries = raw if isinstance(raw, list) else raw.get("connectors", [])
    stubs: list[ConnectorStub] = []
    for entry in entries:
        try:
            kind = ConnectorKind(entry.get("kind", "custom"))
        except ValueError:
            kind = ConnectorKind.CUSTOM
        stubs.append(
            ConnectorStub(
                _config=ConnectorConfig(
                    name=entry.get("name", "unnamed"),
                    kind=kind,
                    config=entry.get("config", {}),
                )
            )
        )
    return stubs


def _load_skills(skills_dir: Path) -> list[SkillEntry]:
    """Scan ``skills/`` for markdown skill files."""
    if not skills_dir.is_dir():
        return []

    entries: list[SkillEntry] = []
    for path in sorted(skills_dir.rglob("*.md")):
        if path.name.startswith("_") or path.name.startswith("."):
            continue
        try:
            entries.append(load_skill_file(path))
        except SkillLoadError as exc:
            logger.warning("Skipping skill %s: %s", path, exc)
    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_plugin(
    plugin_dir: str | Path,
    *,
    sandbox_runner: SandboxRunner | None = None,
) -> PluginEntry:
    """Load a complete Plugin Bundle from *plugin_dir*.

    Validates the manifest, loads agents / skills / connectors, and
    optionally attaches a sandbox runner for script execution.

    Raises :class:`PluginLoadError` on structural errors.
    """
    plugin_dir = Path(plugin_dir)
    if not plugin_dir.is_dir():
        raise PluginLoadError(f"Plugin directory not found: {plugin_dir}")

    manifest = parse_manifest(plugin_dir / "plugin.json")

    agents = _load_agents(plugin_dir / "agents")
    skills = _load_skills(plugin_dir / "skills")
    connectors = _load_connectors(plugin_dir / "connectors" / "connectors.json")

    entry = PluginEntry(
        _manifest=manifest,
        _agents=agents,
        _skills=skills,
        _connectors=connectors,
        _path=plugin_dir,
        _sandbox_runner=sandbox_runner,
    )

    logger.info(
        "Loaded plugin %r v%s (%d agents, %d skills, %d connectors)",
        manifest.name,
        manifest.version,
        len(agents),
        len(skills),
        len(connectors),
    )
    return entry


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

class PluginRegistry:
    """In-memory name → :class:`PluginEntry` registry."""

    def __init__(self) -> None:
        self._entries: dict[str, PluginEntry] = {}

    def register(self, entry: PluginEntry) -> None:
        name = entry.manifest.name
        if name in self._entries:
            raise PluginLoadError(
                f"Plugin {name!r} already registered"
            )
        self._entries[name] = entry

    def get(self, name: str) -> PluginEntry | None:
        return self._entries.get(name)

    def list_plugins(self) -> Sequence[PluginEntry]:
        return list(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def clear(self) -> None:
        self._entries.clear()


__all__ = [
    "AgentStub",
    "ConnectorStub",
    "PluginEntry",
    "PluginLoadError",
    "PluginManifestError",
    "PluginRegistry",
    "SandboxRunner",
    "load_plugin",
    "parse_manifest",
]
