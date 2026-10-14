"""Agent specs — agents are data, not code.

Each ``*.yaml`` / ``*.json`` file in the agents directory declares one
agent::

    name: researcher
    title: Researcher
    description: Finds and reads sources on the web.
    instructions: |
      You are a meticulous researcher ...
    toolkits: [web, commerce-demo]
    skills: "*"            # all skills, a list of names, or [] for none
    memory: false          # per-user long-term memory tools
    delegates: []          # agents this one may hand tasks to
    max_turns: 6
    temperature: 0.2
    model: null            # optional provider override, e.g. "qwen:qwen-plus"

The bundled specs (``agentcook_app/agents/``) define a three-agent team —
``assistant`` (default, delegates to the other two), ``researcher`` and
``analyst`` — so multi-agent delegation works out of the box. Point
``AGENTCOOK_AGENTS_DIR`` at your own directory to replace them.

Delegation is one level deep by design: sub-agents receive their own
toolkits and skills but no delegate tools, which keeps cost and latency
bounded and makes cycles impossible.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")


class AgentSpecError(ValueError):
    """An agent spec file is invalid."""


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    title: str
    description: str
    instructions: str
    toolkits: tuple[str, ...] = ("core",)
    skills: tuple[str, ...] | None = None  # None → all skills
    memory: bool = False
    delegates: tuple[str, ...] = ()
    max_turns: int | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "toolkits": list(self.toolkits),
            "skills": "*" if self.skills is None else list(self.skills),
            "memory": self.memory,
            "delegates": list(self.delegates),
            "max_turns": self.max_turns,
            "model": self.model,
        }


def _tuple_of_str(value: Any, field_name: str, source: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(value)
    raise AgentSpecError(f"{source}: '{field_name}' must be a list of strings")


def parse_agent_spec(raw: Mapping[str, Any], *, source: str = "<inline>") -> AgentSpec:
    name = raw.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise AgentSpecError(f"{source}: 'name' must match {_NAME_RE.pattern}")
    instructions = raw.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        raise AgentSpecError(f"{source}: 'instructions' is required")
    skills_raw = raw.get("skills", "*")
    skills = None if skills_raw in ("*", None) else _tuple_of_str(skills_raw, "skills", source)
    known = {
        "name",
        "title",
        "description",
        "instructions",
        "toolkits",
        "skills",
        "memory",
        "delegates",
        "max_turns",
        "temperature",
        "max_tokens",
        "model",
        "metadata",
    }
    unknown = set(raw) - known
    if unknown:
        raise AgentSpecError(f"{source}: unknown field(s): {', '.join(sorted(unknown))}")
    try:
        return AgentSpec(
            name=name,
            title=str(raw.get("title") or name.replace("-", " ").title()),
            description=str(raw.get("description") or "").strip(),
            instructions=instructions.strip(),
            toolkits=_tuple_of_str(raw.get("toolkits", ["core"]), "toolkits", source),
            skills=skills,
            memory=bool(raw.get("memory", False)),
            delegates=_tuple_of_str(raw.get("delegates"), "delegates", source),
            max_turns=int(raw["max_turns"]) if raw.get("max_turns") is not None else None,
            temperature=float(raw["temperature"]) if raw.get("temperature") is not None else None,
            max_tokens=int(raw["max_tokens"]) if raw.get("max_tokens") is not None else None,
            model=str(raw["model"]) if raw.get("model") else None,
            metadata=dict(raw.get("metadata") or {}),
        )
    except (TypeError, ValueError) as exc:
        raise AgentSpecError(f"{source}: {exc}") from exc


def load_agent_specs(directory: Path) -> list[AgentSpec]:
    if not directory.is_dir():
        raise AgentSpecError(f"agents directory not found: {directory}")
    specs: list[AgentSpec] = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in (".yaml", ".yml", ".json") or path.name.startswith(
            (".", "_")
        ):
            continue
        text = path.read_text(encoding="utf-8")
        try:
            raw = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise AgentSpecError(f"{path}: invalid syntax: {exc}") from exc
        if not isinstance(raw, dict):
            raise AgentSpecError(f"{path}: top level must be a mapping")
        specs.append(parse_agent_spec(raw, source=str(path)))
    return specs


class AgentCatalog:
    """Validated set of agent specs."""

    def __init__(self, specs: Iterable[AgentSpec], *, default: str) -> None:
        self._specs: dict[str, AgentSpec] = {}
        for spec in specs:
            if spec.name in self._specs:
                raise AgentSpecError(f"duplicate agent name {spec.name!r}")
            self._specs[spec.name] = spec
        if not self._specs:
            raise AgentSpecError("no agents defined")
        for spec in self._specs.values():
            missing = [d for d in spec.delegates if d not in self._specs]
            if missing:
                raise AgentSpecError(
                    f"agent {spec.name!r} delegates to unknown agent(s): {missing}"
                )
            if spec.name in spec.delegates:
                raise AgentSpecError(f"agent {spec.name!r} cannot delegate to itself")
        if default not in self._specs:
            raise AgentSpecError(
                f"default agent {default!r} not found; available: {', '.join(self._specs)}"
            )
        self.default = default

    def get(self, name: str | None) -> AgentSpec | None:
        return self._specs.get(name or self.default)

    def list(self) -> list[AgentSpec]:
        """Default agent first, then alphabetical."""
        return sorted(self._specs.values(), key=lambda s: (s.name != self.default, s.name))

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    def validate_toolkits(self, known: Iterable[str]) -> None:
        known_set = set(known)
        for spec in self._specs.values():
            unknown = [t for t in spec.toolkits if t not in known_set]
            if unknown:
                raise AgentSpecError(f"agent {spec.name!r} uses unknown toolkit(s): {unknown}")


__all__ = [
    "AgentCatalog",
    "AgentSpec",
    "AgentSpecError",
    "load_agent_specs",
    "parse_agent_spec",
]
