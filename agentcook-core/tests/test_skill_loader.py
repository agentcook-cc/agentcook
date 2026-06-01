"""Tests for agentcook_core.skill_loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentcook_core.protocols import SkillProtocol
from agentcook_core.skill_loader import (
    SkillConflictError,
    SkillLoadError,
    SkillRegistry,
    load_skill_file,
    manifest_from_frontmatter,
    parse_frontmatter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_SKILL = """\
---
name: greeting-skill
description: Teaches the agent to greet users politely
version: 1.2.0
---
## Greeting Instructions

Always start with "Hello!" and address the user by name.
"""

MINIMAL_SKILL = """\
---
name: minimal
description: bare minimum
---
Body text here.
"""

NO_VERSION_SKILL = """\
---
name: no-ver
description: missing version field
---
Should default to 0.0.0.
"""


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    """Create a temp directory with 2 valid skills and 1 invalid file."""
    (tmp_path / "greeting.md").write_text(VALID_SKILL)
    (tmp_path / "minimal.md").write_text(MINIMAL_SKILL)
    (tmp_path / "broken.md").write_text("no frontmatter here")
    (tmp_path / "readme.txt").write_text("not a skill")
    (tmp_path / "_hidden.md").write_text("---\nname: hidden\ndescription: x\n---\n")
    return tmp_path


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    @pytest.mark.unit
    def test_valid(self):
        meta, body = parse_frontmatter(VALID_SKILL)
        assert meta["name"] == "greeting-skill"
        assert meta["description"] == "Teaches the agent to greet users politely"
        assert meta["version"] == "1.2.0"
        assert "Greeting Instructions" in body

    @pytest.mark.unit
    def test_no_opening_fence(self):
        with pytest.raises(SkillLoadError, match="must begin with"):
            parse_frontmatter("name: oops\n---\nbody")

    @pytest.mark.unit
    def test_no_closing_fence(self):
        with pytest.raises(SkillLoadError, match="No closing"):
            parse_frontmatter("---\nname: oops\n")

    @pytest.mark.unit
    def test_empty_lines_before_fence(self):
        text = "\n\n---\nname: ok\ndescription: ok\n---\nbody"
        meta, body = parse_frontmatter(text)
        assert meta["name"] == "ok"
        assert body == "body"

    @pytest.mark.unit
    def test_quoted_values_stripped(self):
        text = '---\nname: "quoted"\ndescription: \'single\'\n---\n'
        meta, _ = parse_frontmatter(text)
        assert meta["name"] == "quoted"
        assert meta["description"] == "single"

    @pytest.mark.unit
    def test_comment_lines_ignored(self):
        text = "---\nname: x\n# comment\ndescription: y\n---\n"
        meta, _ = parse_frontmatter(text)
        assert "name" in meta
        assert "description" in meta

    @pytest.mark.unit
    def test_bad_line_no_colon(self):
        with pytest.raises(SkillLoadError, match="not a 'key: value'"):
            parse_frontmatter("---\nbadline\n---\n")


# ---------------------------------------------------------------------------
# manifest_from_frontmatter
# ---------------------------------------------------------------------------

class TestManifestFromFrontmatter:
    @pytest.mark.unit
    def test_valid(self):
        manifest = manifest_from_frontmatter(
            {"name": "foo", "description": "bar", "version": "2.0.0"}
        )
        assert manifest.name == "foo"
        assert manifest.description == "bar"
        assert manifest.version == "2.0.0"

    @pytest.mark.unit
    def test_missing_name(self):
        with pytest.raises(SkillLoadError, match="missing required 'name'"):
            manifest_from_frontmatter({"description": "bar"})

    @pytest.mark.unit
    def test_missing_description(self):
        with pytest.raises(SkillLoadError, match="missing required 'description'"):
            manifest_from_frontmatter({"name": "foo"})

    @pytest.mark.unit
    def test_default_version(self):
        manifest = manifest_from_frontmatter({"name": "a", "description": "b"})
        assert manifest.version == "0.0.0"


# ---------------------------------------------------------------------------
# SkillEntry
# ---------------------------------------------------------------------------

class TestSkillEntry:
    @pytest.mark.unit
    def test_satisfies_protocol(self, tmp_path: Path):
        path = tmp_path / "s.md"
        path.write_text(VALID_SKILL)
        entry = load_skill_file(path)
        assert isinstance(entry, SkillProtocol)

    @pytest.mark.unit
    def test_load_body_cached(self, tmp_path: Path):
        path = tmp_path / "s.md"
        path.write_text(VALID_SKILL)
        entry = load_skill_file(path)
        body1 = entry.load()
        body2 = entry.load()
        assert body1 is body2
        assert "Greeting Instructions" in body1

    @pytest.mark.unit
    def test_manifest_fields(self, tmp_path: Path):
        path = tmp_path / "s.md"
        path.write_text(VALID_SKILL)
        entry = load_skill_file(path)
        assert entry.manifest.name == "greeting-skill"
        assert entry.manifest.version == "1.2.0"


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    @pytest.mark.unit
    def test_register_and_get(self, tmp_path: Path):
        path = tmp_path / "s.md"
        path.write_text(VALID_SKILL)
        entry = load_skill_file(path)

        reg = SkillRegistry()
        reg.register(entry)
        assert len(reg) == 1
        assert "greeting-skill" in reg
        assert reg.get("greeting-skill") is entry

    @pytest.mark.unit
    def test_duplicate_raises(self, tmp_path: Path):
        path = tmp_path / "s.md"
        path.write_text(VALID_SKILL)
        entry = load_skill_file(path)

        reg = SkillRegistry()
        reg.register(entry)
        with pytest.raises(SkillConflictError):
            reg.register(entry)

    @pytest.mark.unit
    def test_register_directory(self, skill_dir: Path):
        reg = SkillRegistry()
        entries = reg.register_directory(skill_dir)
        # greeting.md + minimal.md should load; broken.md skipped; _hidden.md skipped
        assert len(entries) == 2
        assert len(reg) == 2
        names = {e.manifest.name for e in entries}
        assert "greeting-skill" in names
        assert "minimal" in names

    @pytest.mark.unit
    def test_register_directory_not_found(self):
        reg = SkillRegistry()
        with pytest.raises(FileNotFoundError):
            reg.register_directory("/nonexistent/path")

    @pytest.mark.unit
    def test_list_skills(self, tmp_path: Path):
        path = tmp_path / "s.md"
        path.write_text(VALID_SKILL)
        entry = load_skill_file(path)

        reg = SkillRegistry()
        reg.register(entry)
        skills = reg.list_skills()
        assert len(skills) == 1

    @pytest.mark.unit
    def test_clear(self, tmp_path: Path):
        path = tmp_path / "s.md"
        path.write_text(VALID_SKILL)
        entry = load_skill_file(path)

        reg = SkillRegistry()
        reg.register(entry)
        reg.clear()
        assert len(reg) == 0

    @pytest.mark.unit
    def test_get_missing(self):
        reg = SkillRegistry()
        assert reg.get("nope") is None
