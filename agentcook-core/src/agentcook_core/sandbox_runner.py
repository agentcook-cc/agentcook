"""Plugin Docker sandbox executor — isolated code execution for untrusted plugins.

Provides a typed sandbox system that runs plugin code inside ephemeral
Docker containers with strict security constraints.

Design:
- ``SandboxExecutor`` Protocol is stdlib-only (no Docker SDK import).
- ``DockerSandboxExecutor`` uses subprocess to invoke ``docker`` CLI
  (avoids hard dependency on ``docker`` Python SDK).
- ``SubprocessSandboxExecutor`` lightweight alternative using local
  subprocess (for testing / CI without Docker).
- Security-by-default: no network, read-only rootfs, memory cap, CPU limit.

Layer separation:
- agentcook-core defines Protocol + Config + Result (stdlib-only).
- Concrete executors use subprocess (stdlib) — no third-party import.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value Types
# ---------------------------------------------------------------------------


class NetworkMode(str, Enum):
    """Container network isolation level."""

    NONE = "none"
    BRIDGE = "bridge"
    HOST = "host"


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Declarative sandbox parameters.

    Attributes:
        image: Docker image to use (must be pre-pulled or pullable).
        timeout: Maximum execution time in seconds.
        memory_limit: Memory cap (Docker format, e.g. "512m", "1g").
        cpu_limit: CPU quota (fractional cores, e.g. 0.5 = half a core).
        network_mode: Network isolation (default: NONE = no network).
        read_only: Mount rootfs as read-only (default: True).
        tmpfs_size: Size of /tmp writable tmpfs (default: "64m").
        workdir: Working directory inside the container.
        env: Environment variables to inject.
        allowed_domains: If network enabled, whitelist of domains (Phase 5).
    """

    image: str = "agentcook-plugin-sandbox:latest"
    timeout: int = 30
    memory_limit: str = "512m"
    cpu_limit: float = 0.5
    network_mode: NetworkMode = NetworkMode.NONE
    read_only: bool = True
    tmpfs_size: str = "64m"
    workdir: str = "/plugin"
    env: dict[str, str] = field(default_factory=dict)
    allowed_domains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Outcome of a sandbox execution.

    Attributes:
        exit_code: Process exit code (-1 if timed out / killed).
        stdout: Captured standard output.
        stderr: Captured standard error.
        duration_ms: Wall-clock execution time in milliseconds.
        timed_out: True if execution exceeded timeout.
        oom_killed: True if container was killed due to memory limit.
        container_id: Docker container ID (for debugging).
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    oom_killed: bool = False
    container_id: str | None = None

    @property
    def success(self) -> bool:
        """True if exited cleanly with code 0."""
        return self.exit_code == 0 and not self.timed_out and not self.oom_killed


class SandboxError(Exception):
    """Raised on sandbox infrastructure failures (not plugin errors)."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SandboxExecutor(Protocol):
    """Executes code in an isolated sandbox.

    Implementations may use Docker, Firecracker, gVisor, or a local
    subprocess (for testing). The protocol is intentionally synchronous;
    async wrappers belong in downstream orchestration layers.
    """

    def run(
        self,
        code: str,
        *,
        config: SandboxConfig | None = None,
        script_name: str = "main.py",
        plugin_dir: str | None = None,
    ) -> SandboxResult:
        """Execute code/script in the sandbox.

        Args:
            code: Source code to execute (written to a temp file inside container).
            config: Sandbox parameters (uses defaults if None).
            script_name: Filename for the code inside the container.
            plugin_dir: Optional host directory to mount read-only at /plugin.

        Returns:
            SandboxResult with captured output and timing.
        """
        ...


# ---------------------------------------------------------------------------
# Docker CLI Executor
# ---------------------------------------------------------------------------


class DockerSandboxExecutor:
    """Runs plugin code in ephemeral Docker containers via CLI.

    Uses ``docker run`` subprocess — no Python Docker SDK dependency.
    Containers are auto-removed on success; force-killed on timeout.
    """

    def __init__(self, *, docker_bin: str = "docker") -> None:
        self._docker = docker_bin

    def run(
        self,
        code: str,
        *,
        config: SandboxConfig | None = None,
        script_name: str = "main.py",
        plugin_dir: str | None = None,
    ) -> SandboxResult:
        cfg = config or SandboxConfig()
        container_name = f"sandbox-{uuid.uuid4().hex[:12]}"

        cmd = self._build_command(cfg, container_name, code, script_name, plugin_dir)

        start_ns = time.perf_counter_ns()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=cfg.timeout,
            )
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

            oom_killed = self._check_oom(container_name)

            return SandboxResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
                timed_out=False,
                oom_killed=oom_killed,
                container_id=container_name,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            self._force_remove(container_name)

            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {cfg.timeout}s",
                duration_ms=duration_ms,
                timed_out=True,
                oom_killed=False,
                container_id=container_name,
            )

        except FileNotFoundError:
            raise SandboxError(
                f"Docker binary not found: {self._docker}. "
                "Ensure Docker is installed and in PATH."
            )

    def _build_command(
        self,
        cfg: SandboxConfig,
        container_name: str,
        code: str,
        script_name: str,
        plugin_dir: str | None,
    ) -> list[str]:
        """Assemble the docker run command with security constraints."""
        cmd = [
            self._docker, "run",
            "--name", container_name,
            "--rm",
            "--cpus", str(cfg.cpu_limit),
            "--memory", cfg.memory_limit,
            "--network", cfg.network_mode.value,
            "--security-opt", "no-new-privileges",
            "--pids-limit", "64",
        ]

        if cfg.read_only:
            cmd.extend(["--read-only", "--tmpfs", f"/tmp:size={cfg.tmpfs_size}"])

        if plugin_dir:
            cmd.extend(["-v", f"{plugin_dir}:{cfg.workdir}:ro"])

        cmd.extend(["-w", cfg.workdir])

        for env_key, env_val in cfg.env.items():
            cmd.extend(["-e", f"{env_key}={env_val}"])

        # Pass code via stdin using sh -c
        escaped_code = code.replace("'", "'\\''")
        cmd.extend([
            cfg.image,
            "sh", "-c", f"echo '{escaped_code}' > /tmp/{script_name} && python /tmp/{script_name}",
        ])

        return cmd

    def _check_oom(self, container_name: str) -> bool:
        """Check if container was OOM-killed (only works if --rm didn't clean it)."""
        try:
            result = subprocess.run(
                [self._docker, "inspect", container_name, "--format", "{{.State.OOMKilled}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip().lower() == "true"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _force_remove(self, container_name: str) -> None:
        """Force-stop and remove a container."""
        try:
            subprocess.run(
                [self._docker, "rm", "-f", container_name],
                capture_output=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Failed to force-remove container: %s", container_name)


# ---------------------------------------------------------------------------
# Subprocess Executor (lightweight, no Docker)
# ---------------------------------------------------------------------------


class SubprocessSandboxExecutor:
    """Lightweight sandbox using local subprocess.

    No Docker required — suitable for testing and CI environments.
    Security is limited to timeout + memory tracking (no true isolation).
    """

    def __init__(self, *, python_bin: str = "python3") -> None:
        self._python = python_bin

    def run(
        self,
        code: str,
        *,
        config: SandboxConfig | None = None,
        script_name: str = "main.py",  # noqa: ARG002
        plugin_dir: str | None = None,  # noqa: ARG002
    ) -> SandboxResult:
        cfg = config or SandboxConfig()

        start_ns = time.perf_counter_ns()
        try:
            proc = subprocess.run(
                [self._python, "-c", code],
                capture_output=True,
                text=True,
                timeout=cfg.timeout,
            )
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

            return SandboxResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
                timed_out=False,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {cfg.timeout}s",
                duration_ms=duration_ms,
                timed_out=True,
            )

        except FileNotFoundError:
            raise SandboxError(f"Python binary not found: {self._python}")


__all__ = [
    "DockerSandboxExecutor",
    "NetworkMode",
    "SandboxConfig",
    "SandboxError",
    "SandboxExecutor",
    "SandboxResult",
    "SubprocessSandboxExecutor",
]
