"""Skill loader: scan directories for Skill markdown bundles, parse
frontmatter into :class:`SkillManifest`, and maintain an in-memory
registry.

Design decisions (see ADR-001 / ADR-012):
- **stdlib-only**: no ``pyyaml`` dependency — frontmatter is parsed with
  a minimal key-value parser sufficient for the 3-field manifest
  (``name``, ``description``, ``version``).
- **Lazy body loading**: the markdown body is read on first
  ``SkillEntry.load()`` and cached.  Subsequent calls return the cache.
- **Registry is additive**: ``register`` / ``register_directory`` append;
  duplicates raise ``SkillConflictError``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from agentcook_core.protocols import SkillProtocol
from agentcook_core.types import SkillManifest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SkillLoadError(Exception):
    """Raised when a skill file cannot be parsed."""


class SkillConflictError(Exception):
    """Raised when two skills share the same name."""


# ---------------------------------------------------------------------------
# Frontmatter parser (stdlib-only, no pyyaml)
# ---------------------------------------------------------------------------

_FENCE = "---"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML-style frontmatter delimited by ``---`` fences.

    Returns ``(metadata_dict, body)`` where *body* is everything after
    the closing fence.  Only simple ``key: value`` pairs are supported —
    nested structures / lists are outside scope for skill manifests.

    Raises :class:`SkillLoadError` if fences are missing or malformed.
    """
    lines = text.split("\n")

    # Find opening fence
    start = -1
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == _FENCE:
            start = index
            break
        if stripped:
            raise SkillLoadError(
                "Skill file must begin with '---' frontmatter fence "
                f"(found {stripped!r} on line {index + 1})"
            )

    if start == -1:
        raise SkillLoadError("No opening '---' frontmatter fence found")

    # Find closing fence
    end = -1
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == _FENCE:
            end = index
            break

    if end == -1:
        raise SkillLoadError("No closing '---' frontmatter fence found")

    # Parse key: value pairs between fences
    metadata: dict[str, str] = {}
    for line_number in range(start + 1, end):
        raw = lines[line_number].strip()
        if not raw or raw.startswith("#"):
            continue
        if ":" not in raw:
            raise SkillLoadError(
                f"Frontmatter line {line_number + 1} is not a 'key: value' pair: {raw!r}"
            )
        key, _, value = raw.partition(":")
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    body = "\n".join(lines[end + 1 :]).strip()
    return metadata, body


def manifest_from_frontmatter(metadata: dict[str, str], *, source: str = "<unknown>") -> SkillManifest:
    """Build a :class:`SkillManifest` from parsed frontmatter *metadata*.

    ``name`` and ``description`` are required; ``version`` defaults to
    ``"0.0.0"`` if absent.
    """
    name = metadata.get("name")
    if not name:
        raise SkillLoadError(f"Skill frontmatter missing required 'name' field ({source})")

    description = metadata.get("description")
    if not description:
        raise SkillLoadError(f"Skill frontmatter missing required 'description' field ({source})")

    return SkillManifest(
        name=name,
        description=description,
        version=metadata.get("version", "0.0.0"),
    )


# ---------------------------------------------------------------------------
# SkillEntry — a loaded Skill satisfying SkillProtocol
# ---------------------------------------------------------------------------

@dataclass
class SkillEntry:
    """Concrete :class:`SkillProtocol` implementation backed by a file.

    The markdown body is lazily cached on first :meth:`load` call.
    """

    _manifest: SkillManifest
    _path: Path
    _body_cache: str | None = field(default=None, repr=False)

    @property
    def manifest(self) -> SkillManifest:
        return self._manifest

    def load(self) -> str:
        if self._body_cache is not None:
            return self._body_cache
        text = self._path.read_text(encoding="utf-8")
        _, body = parse_frontmatter(text)
        self._body_cache = body
        return body


# Runtime check — SkillEntry must satisfy SkillProtocol
assert isinstance(SkillEntry.__new__(SkillEntry), SkillProtocol), (
    "SkillEntry does not satisfy SkillProtocol"
)


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """In-memory name → :class:`SkillEntry` registry.

    Thread-safety note: the registry is intended for single-threaded
    startup registration followed by read-only lookups at runtime.
    """

    def __init__(self) -> None:
        self._entries: dict[str, SkillEntry] = {}

    # -- mutators -----------------------------------------------------------

    def register(self, entry: SkillEntry) -> None:
        """Add a single skill; raises :class:`SkillConflictError` on dup."""
        name = entry.manifest.name
        if name in self._entries:
            raise SkillConflictError(
                f"Skill {name!r} already registered "
                f"(existing: {self._entries[name]._path}, "
                f"new: {entry._path})"
            )
        self._entries[name] = entry
        logger.debug("Registered skill %r from %s", name, entry._path)

    def register_directory(self, directory: str | Path) -> list[SkillEntry]:
        """Scan *directory* for ``*.md`` files, parse each, and register.

        Returns the list of newly registered entries.  Non-markdown files
        are silently skipped.
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise FileNotFoundError(f"Skill directory not found: {directory}")

        registered: list[SkillEntry] = []
        for path in sorted(directory.rglob("*.md")):
            if path.name.startswith("_") or path.name.startswith("."):
                continue
            try:
                entry = load_skill_file(path)
            except SkillLoadError as exc:
                logger.warning("Skipping %s: %s", path, exc)
                continue
            self.register(entry)
            registered.append(entry)

        logger.info(
            "Registered %d skills from %s", len(registered), directory
        )
        return registered

    # -- queries ------------------------------------------------------------

    def get(self, name: str) -> SkillEntry | None:
        """Look up a skill by name; ``None`` if not found."""
        return self._entries.get(name)

    def list_skills(self) -> Sequence[SkillEntry]:
        """Return all registered skills (insertion order)."""
        return list(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def clear(self) -> None:
        """Remove all entries (useful in tests)."""
        self._entries.clear()


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def load_skill_file(path: str | Path) -> SkillEntry:
    """Parse a single ``.md`` file into a :class:`SkillEntry`.

    Raises :class:`SkillLoadError` on parse failures.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    metadata, _ = parse_frontmatter(text)
    manifest = manifest_from_frontmatter(metadata, source=str(path))
    return SkillEntry(_manifest=manifest, _path=path)


__all__ = [
    "SkillConflictError",
    "SkillEntry",
    "SkillLoadError",
    "SkillRegistry",
    "load_skill_file",
    "manifest_from_frontmatter",
    "parse_frontmatter",
]
