"""Unit tests for agentcook_core.sandbox_runner module."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agentcook_core.sandbox_runner import (
    DockerSandboxExecutor,
    NetworkMode,
    SandboxConfig,
    SandboxError,
    SandboxExecutor,
    SandboxResult,
    SubprocessSandboxExecutor,
)


# ---------------------------------------------------------------------------
# SandboxConfig Tests
# ---------------------------------------------------------------------------


class TestSandboxConfig:
    def test_frozen_immutable(self):
        cfg = SandboxConfig()
        with pytest.raises(AttributeError):
            cfg.timeout = 60  # type: ignore[misc]

    def test_defaults(self):
        cfg = SandboxConfig()
        assert cfg.image == "agentcook-plugin-sandbox:latest"
        assert cfg.timeout == 30
        assert cfg.memory_limit == "512m"
        assert cfg.cpu_limit == 0.5
        assert cfg.network_mode == NetworkMode.NONE
        assert cfg.read_only is True
        assert cfg.tmpfs_size == "64m"
        assert cfg.workdir == "/plugin"
        assert cfg.env == {}
        assert cfg.allowed_domains == ()

    def test_custom_config(self):
        cfg = SandboxConfig(
            image="python:3.12-slim",
            timeout=60,
            memory_limit="1g",
            cpu_limit=1.0,
            network_mode=NetworkMode.BRIDGE,
            env={"API_KEY": "test"},
        )
        assert cfg.image == "python:3.12-slim"
        assert cfg.timeout == 60
        assert cfg.network_mode == NetworkMode.BRIDGE
        assert cfg.env == {"API_KEY": "test"}


# ---------------------------------------------------------------------------
# SandboxResult Tests
# ---------------------------------------------------------------------------


class TestSandboxResult:
    def test_success_property(self):
        result = SandboxResult(exit_code=0, stdout="ok", stderr="", duration_ms=100.0)
        assert result.success is True

    def test_failure_nonzero_exit(self):
        result = SandboxResult(exit_code=1, stdout="", stderr="err", duration_ms=50.0)
        assert result.success is False

    def test_failure_timed_out(self):
        result = SandboxResult(exit_code=-1, stdout="", stderr="timeout", duration_ms=30000.0, timed_out=True)
        assert result.success is False

    def test_failure_oom(self):
        result = SandboxResult(exit_code=-1, stdout="", stderr="", duration_ms=500.0, oom_killed=True)
        assert result.success is False

    def test_frozen(self):
        result = SandboxResult(exit_code=0, stdout="", stderr="", duration_ms=0.0)
        with pytest.raises(AttributeError):
            result.exit_code = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# NetworkMode Tests
# ---------------------------------------------------------------------------


class TestNetworkMode:
    def test_all_modes(self):
        assert {m.value for m in NetworkMode} == {"none", "bridge", "host"}

    def test_default_is_none(self):
        cfg = SandboxConfig()
        assert cfg.network_mode == NetworkMode.NONE


# ---------------------------------------------------------------------------
# DockerSandboxExecutor Tests (mocked)
# ---------------------------------------------------------------------------


class TestDockerSandboxExecutor:
    def test_protocol_compliance(self):
        assert isinstance(DockerSandboxExecutor(), SandboxExecutor)

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_successful_execution(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="hello world\n", stderr=""
        )
        executor = DockerSandboxExecutor()
        result = executor.run("print('hello world')")

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "hello world\n"
        assert result.timed_out is False
        assert result.duration_ms > 0

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_nonzero_exit_code(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="SyntaxError"
        )
        executor = DockerSandboxExecutor()
        result = executor.run("invalid python{{{")

        assert result.success is False
        assert result.exit_code == 1
        assert "SyntaxError" in result.stderr

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_timeout_handling(self, mock_run: MagicMock):
        # First call (docker run) raises timeout
        # Second call (docker rm -f) succeeds
        mock_run.side_effect = [
            subprocess.TimeoutExpired(cmd="docker run", timeout=5),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]
        executor = DockerSandboxExecutor()
        config = SandboxConfig(timeout=5)
        result = executor.run("import time; time.sleep(100)", config=config)

        assert result.timed_out is True
        assert result.exit_code == -1
        assert "timed out" in result.stderr

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_docker_not_found_raises(self, mock_run: MagicMock):
        mock_run.side_effect = FileNotFoundError()
        executor = DockerSandboxExecutor()

        with pytest.raises(SandboxError, match="Docker binary not found"):
            executor.run("print(1)")

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_command_includes_security_flags(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        executor = DockerSandboxExecutor()
        executor.run("print(1)")

        # First call is docker run; subsequent calls are _check_oom inspect
        call_args = mock_run.call_args_list[0][0][0]
        assert "--network" in call_args
        assert "none" in call_args
        assert "--read-only" in call_args
        assert "--security-opt" in call_args
        assert "no-new-privileges" in call_args
        assert "--cpus" in call_args
        assert "--memory" in call_args
        assert "--pids-limit" in call_args

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_custom_config_applied(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        config = SandboxConfig(
            image="python:3.12",
            network_mode=NetworkMode.BRIDGE,
            memory_limit="1g",
            cpu_limit=2.0,
            env={"FOO": "bar"},
        )
        executor = DockerSandboxExecutor()
        executor.run("print(1)", config=config)

        call_args = mock_run.call_args_list[0][0][0]
        assert "python:3.12" in call_args
        assert "bridge" in call_args
        assert "1g" in call_args
        assert "2.0" in call_args
        assert "FOO=bar" in call_args

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_plugin_dir_mounted(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        executor = DockerSandboxExecutor()
        executor.run("print(1)", plugin_dir="/path/to/plugin")

        call_args = mock_run.call_args_list[0][0][0]
        assert "-v" in call_args
        assert "/path/to/plugin:/plugin:ro" in call_args

    @patch("agentcook_core.sandbox_runner.subprocess.run")
    def test_container_id_in_result(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        executor = DockerSandboxExecutor()
        result = executor.run("print(1)")
        assert result.container_id is not None
        assert result.container_id.startswith("sandbox-")


# ---------------------------------------------------------------------------
# SubprocessSandboxExecutor Tests
# ---------------------------------------------------------------------------


class TestSubprocessSandboxExecutor:
    def test_protocol_compliance(self):
        assert isinstance(SubprocessSandboxExecutor(), SandboxExecutor)

    def test_successful_execution(self):
        executor = SubprocessSandboxExecutor()
        result = executor.run("print('hello')")
        assert result.success is True
        assert result.stdout.strip() == "hello"
        assert result.exit_code == 0

    def test_syntax_error(self):
        executor = SubprocessSandboxExecutor()
        result = executor.run("def broken(")
        assert result.success is False
        assert result.exit_code != 0
        assert "SyntaxError" in result.stderr

    def test_timeout(self):
        executor = SubprocessSandboxExecutor()
        config = SandboxConfig(timeout=1)
        result = executor.run("import time; time.sleep(10)", config=config)
        assert result.timed_out is True
        assert result.exit_code == -1

    def test_duration_recorded(self):
        executor = SubprocessSandboxExecutor()
        result = executor.run("print(1+1)")
        assert result.duration_ms > 0

    def test_python_not_found_raises(self):
        executor = SubprocessSandboxExecutor(python_bin="/nonexistent/python999")
        with pytest.raises(SandboxError, match="Python binary not found"):
            executor.run("print(1)")

    def test_multiline_code(self):
        executor = SubprocessSandboxExecutor()
        code = "x = 42\nprint(x * 2)"
        result = executor.run(code)
        assert result.success is True
        assert result.stdout.strip() == "84"

    def test_stderr_captured(self):
        executor = SubprocessSandboxExecutor()
        code = "import sys; sys.stderr.write('warning\\n')"
        result = executor.run(code)
        assert "warning" in result.stderr


# ---------------------------------------------------------------------------
# Protocol Compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_docker_executor_satisfies_protocol(self):
        assert isinstance(DockerSandboxExecutor(), SandboxExecutor)

    def test_subprocess_executor_satisfies_protocol(self):
        assert isinstance(SubprocessSandboxExecutor(), SandboxExecutor)
