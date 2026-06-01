"""Tests for agentcook_core.plugin_loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentcook_core.plugin_loader import (
    PluginLoadError,
    PluginManifestError,
    PluginRegistry,
    load_plugin,
    parse_manifest,
)
from agentcook_core.protocols import PluginProtocol
from agentcook_core.types import ConnectorKind

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MANIFEST = {
    "name": "test-plugin",
    "display_name": "Test Plugin",
    "version": "1.0.0",
    "description": "A test plugin",
    "author": "tester",
    "category": "demo",
    "default_agent": "main-agent",
}

AGENT_JSON = {
    "name": "main-agent",
    "description": "The main agent",
    "model": {"provider": "openai", "name": "gpt-4o"},
}

SKILL_MD = """\
---
name: demo-skill
description: A demo skill for testing
version: 0.1.0
---
## Demo

Do the thing.
"""

CONNECTORS_JSON = [
    {"name": "github", "kind": "oauth", "config": {"client_id": "xxx"}},
    {"name": "local-mcp", "kind": "mcp", "config": {"endpoint": "http://localhost:3000"}},
]


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """Create a full plugin bundle on disk."""
    # plugin.json
    (tmp_path / "plugin.json").write_text(json.dumps(MANIFEST))

    # agents/main-agent/agent.json
    agents_dir = tmp_path / "agents" / "main-agent"
    agents_dir.mkdir(parents=True)
    (agents_dir / "agent.json").write_text(json.dumps(AGENT_JSON))

    # skills/demo-skill.md
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "demo-skill.md").write_text(SKILL_MD)

    # connectors/connectors.json
    conn_dir = tmp_path / "connectors"
    conn_dir.mkdir()
    (conn_dir / "connectors.json").write_text(json.dumps(CONNECTORS_JSON))

    return tmp_path


@pytest.fixture
def minimal_plugin_dir(tmp_path: Path) -> Path:
    """Plugin with only manifest — no agents/skills/connectors."""
    (tmp_path / "plugin.json").write_text(json.dumps(MANIFEST))
    return tmp_path


# ---------------------------------------------------------------------------
# parse_manifest
# ---------------------------------------------------------------------------

class TestParseManifest:
    @pytest.mark.unit
    def test_valid(self, tmp_path: Path):
        path = tmp_path / "plugin.json"
        path.write_text(json.dumps(MANIFEST))
        m = parse_manifest(path)
        assert m.name == "test-plugin"
        assert m.display_name == "Test Plugin"
        assert m.version == "1.0.0"
        assert m.author == "tester"

    @pytest.mark.unit
    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(PluginManifestError, match="not found"):
            parse_manifest(tmp_path / "nope.json")

    @pytest.mark.unit
    def test_invalid_json(self, tmp_path: Path):
        path = tmp_path / "plugin.json"
        path.write_text("{bad json")
        with pytest.raises(PluginManifestError, match="Invalid JSON"):
            parse_manifest(path)

    @pytest.mark.unit
    def test_missing_required_fields(self, tmp_path: Path):
        path = tmp_path / "plugin.json"
        path.write_text(json.dumps({"name": "x"}))
        with pytest.raises(PluginManifestError, match="missing required"):
            parse_manifest(path)


# ---------------------------------------------------------------------------
# load_plugin
# ---------------------------------------------------------------------------

class TestLoadPlugin:
    @pytest.mark.unit
    def test_full_bundle(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        assert isinstance(entry, PluginProtocol)
        assert entry.manifest.name == "test-plugin"
        assert len(entry.agents) == 1
        assert len(entry.skills) == 1
        assert len(entry.connectors) == 2

    @pytest.mark.unit
    def test_agent_fields(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        agent = entry.agents[0]
        assert agent.name == "main-agent"
        assert agent.model.provider == "openai"
        assert agent.model.name == "gpt-4o"

    @pytest.mark.unit
    def test_connector_fields(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        names = {c.config.name for c in entry.connectors}
        assert "github" in names
        assert "local-mcp" in names
        kinds = {c.config.kind for c in entry.connectors}
        assert ConnectorKind.OAUTH in kinds
        assert ConnectorKind.MCP in kinds

    @pytest.mark.unit
    def test_skill_loaded(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        skill = entry.skills[0]
        assert skill.manifest.name == "demo-skill"
        body = skill.load()
        assert "Do the thing" in body

    @pytest.mark.unit
    def test_minimal_bundle(self, minimal_plugin_dir: Path):
        entry = load_plugin(minimal_plugin_dir)
        assert entry.manifest.name == "test-plugin"
        assert len(entry.agents) == 0
        assert len(entry.skills) == 0
        assert len(entry.connectors) == 0

    @pytest.mark.unit
    def test_nonexistent_dir(self):
        with pytest.raises(PluginLoadError, match="not found"):
            load_plugin("/nonexistent/plugin/dir")

    @pytest.mark.unit
    def test_sandbox_runner_attached(self, plugin_dir: Path):
        calls: list[tuple] = []

        def fake_sandbox(plugin_dir, script_name, *, timeout=30, cpu_limit=0.5, memory_limit="512m"):
            calls.append((plugin_dir, script_name))
            return None

        entry = load_plugin(plugin_dir, sandbox_runner=fake_sandbox)
        assert entry._sandbox_runner is not None


# ---------------------------------------------------------------------------
# PluginEntry lifecycle
# ---------------------------------------------------------------------------

class TestPluginEntryLifecycle:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_activate_deactivate(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        assert not entry.is_active
        await entry.activate()
        assert entry.is_active
        await entry.activate()  # idempotent
        assert entry.is_active
        await entry.deactivate()
        assert not entry.is_active
        await entry.deactivate()  # idempotent
        assert not entry.is_active


# ---------------------------------------------------------------------------
# PluginRegistry
# ---------------------------------------------------------------------------

class TestPluginRegistry:
    @pytest.mark.unit
    def test_register_and_get(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        reg = PluginRegistry()
        reg.register(entry)
        assert len(reg) == 1
        assert "test-plugin" in reg
        assert reg.get("test-plugin") is entry

    @pytest.mark.unit
    def test_duplicate_raises(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        reg = PluginRegistry()
        reg.register(entry)
        with pytest.raises(PluginLoadError, match="already registered"):
            reg.register(entry)

    @pytest.mark.unit
    def test_list_plugins(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        reg = PluginRegistry()
        reg.register(entry)
        assert len(reg.list_plugins()) == 1

    @pytest.mark.unit
    def test_get_missing(self):
        reg = PluginRegistry()
        assert reg.get("nope") is None

    @pytest.mark.unit
    def test_clear(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        reg = PluginRegistry()
        reg.register(entry)
        reg.clear()
        assert len(reg) == 0


# ---------------------------------------------------------------------------
# AgentStub / ConnectorStub edge cases
# ---------------------------------------------------------------------------

class TestStubs:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_agent_stub_run_raises(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        agent = entry.agents[0]
        with pytest.raises(NotImplementedError, match="metadata-only"):
            await agent.run([])

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connector_stub_open_raises(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        connector = entry.connectors[0]
        with pytest.raises(NotImplementedError, match="wire via runtime"):
            await connector.open()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connector_stub_close_safe(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        connector = entry.connectors[0]
        await connector.close()  # should not raise

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connector_stub_tools_empty(self, plugin_dir: Path):
        entry = load_plugin(plugin_dir)
        connector = entry.connectors[0]
        tools = await connector.tools()
        assert tools == ()
