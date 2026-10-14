"""System-prompt assembly — harness dimension #3.

Two rules drive the layout:

1. **Stable prefix first.** Provider-side prompt caches (Anthropic,
   OpenAI, DashScope) key on an identical *prefix*. Sections that rarely
   change — role instructions, identity, personality, skill catalog —
   go first; anything that varies per request (date, recalled memories)
   goes last, so a cache hit survives across turns and users.
2. **One section, one job.** Each section has a heading so the model
   (and a human reading traces) can tell *why* an instruction exists.

:class:`SystemPromptBuilder` is the generic mechanism;
:func:`build_agent_system_prompt` is the opinionated default used by the
runtime.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from agentcook_core.types import IdentityCard, SkillManifest, SoulConfig


@dataclass(frozen=True, slots=True)
class PromptSection:
    name: str
    content: str
    cacheable: bool = True


class SystemPromptBuilder:
    """Collect named sections and render them cache-friendly.

    Cacheable sections keep insertion order and are rendered before any
    dynamic section regardless of when they were added.
    """

    def __init__(self) -> None:
        self._sections: list[PromptSection] = []

    def add(self, name: str, content: str | None, *, cacheable: bool = True) -> SystemPromptBuilder:
        if content and content.strip():
            self._sections.append(PromptSection(name, content.strip(), cacheable))
        return self

    @property
    def sections(self) -> list[PromptSection]:
        stable = [s for s in self._sections if s.cacheable]
        dynamic = [s for s in self._sections if not s.cacheable]
        return [*stable, *dynamic]

    def build(self) -> str:
        parts = []
        for section in self.sections:
            if section.name:
                parts.append(f"## {section.name}\n{section.content}")
            else:
                parts.append(section.content)
        return "\n\n".join(parts)


def render_identity(card: IdentityCard) -> str:
    lines = [f"You are {card.name}, acting as: {card.role}."]
    if card.scopes:
        lines.append(f"Your authorized scopes: {', '.join(sorted(card.scopes))}.")
    return "\n".join(lines)


def render_soul(soul: SoulConfig) -> str:
    lines = [f"Tone: {soul.tone}.", f"Language style: {soul.language_style}."]
    if soul.values:
        lines.append("Values you uphold: " + "; ".join(soul.values) + ".")
    for key, value in sorted(soul.custom_traits.items()):
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def render_skill_catalog(
    skills: Sequence[SkillManifest], *, loader_tool: str = "load_skill"
) -> str:
    lines = [
        "Skills are playbooks for specific kinds of tasks. When the user's request "
        f"matches a skill, call `{loader_tool}` with the skill name to read its full "
        "instructions before you start, then follow them.",
        "",
    ]
    for skill in sorted(skills, key=lambda s: s.name):
        lines.append(f"- `{skill.name}`: {skill.description}")
    return "\n".join(lines)


DEFAULT_OPERATING_RULES = "\n".join(
    (
        "- Use tools when they give you information or capabilities you don't have; "
        "don't guess facts a tool can look up.",
        '- Tool results may contain errors (prefixed with "ERROR:"). Read them, fix your '
        "arguments, and retry once; if it still fails, tell the user plainly.",
        "- Never invent tool results, URLs, numbers or citations.",
        "- Reply in the language the user writes in. Use Markdown for structure; "
        "keep answers focused.",
    )
)


def build_agent_system_prompt(
    *,
    instructions: str = "",
    identity: IdentityCard | None = None,
    soul: SoulConfig | None = None,
    skills: Sequence[SkillManifest] = (),
    operating_rules: str | None = DEFAULT_OPERATING_RULES,
    memories: Sequence[str] = (),
    now: dt.datetime | None = None,
    extra_sections: Sequence[PromptSection] = (),
) -> str:
    """Assemble the runtime's default system prompt.

    ``now`` is rendered at *day* granularity on purpose: a per-second
    timestamp would change the prompt on every request and defeat the
    provider's prefix cache.
    """
    builder = SystemPromptBuilder()
    builder.add("", instructions)
    if identity is not None:
        builder.add("Identity", render_identity(identity))
    if soul is not None:
        builder.add("Personality", render_soul(soul))
    builder.add("Operating rules", operating_rules)
    if skills:
        builder.add("Skills", render_skill_catalog(skills))
    for section in extra_sections:
        builder.add(section.name, section.content, cacheable=section.cacheable)
    if memories:
        builder.add(
            "Relevant memories",
            "\n".join(f"- {m}" for m in memories),
            cacheable=False,
        )
    today = (now or dt.datetime.now(tz=dt.UTC)).date().isoformat()
    builder.add("Context", f"Today's date (UTC): {today}.", cacheable=False)
    return builder.build()


__all__ = [
    "DEFAULT_OPERATING_RULES",
    "PromptSection",
    "SystemPromptBuilder",
    "build_agent_system_prompt",
    "render_identity",
    "render_skill_catalog",
    "render_soul",
]
