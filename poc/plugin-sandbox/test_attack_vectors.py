"""Attack vector tests for Plugin Docker sandbox.

Prerequisites:
    docker build -t agentcook-plugin-sandbox .

Run:
    python test_attack_vectors.py
"""

import os
import unittest
from sandbox_runner import run_plugin_script

PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "example-plugin")

class TestPluginSandbox(unittest.TestCase):
    """Test that the sandbox blocks all attack vectors."""

    def test_normal_execution(self):
        """Normal script should execute successfully."""
        result = run_plugin_script(PLUGIN_DIR, "hello.py", timeout=10)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello from sandboxed plugin", result.stdout)
        self.assertFalse(result.timed_out)
        self.assertFalse(result.oom_killed)

    def test_read_host_passwd(self):
        """Container /etc/passwd should only show sandbox user, not host."""
        result = run_plugin_script(PLUGIN_DIR, "read_passwd.py", timeout=10)
        # Container has its own /etc/passwd with sandbox user
        # It should NOT contain host-specific users
        if result.exit_code == 0:
            self.assertNotIn("root:x:0:0:root", result.stdout)

    def test_network_escape(self):
        """Network requests should be blocked (--network=none)."""
        result = run_plugin_script(PLUGIN_DIR, "network_escape.py", timeout=10)
        self.assertIn("BLOCKED", result.stdout + result.stderr)

    def test_cpu_bomb(self):
        """Infinite loop should be killed by timeout."""
        result = run_plugin_script(PLUGIN_DIR, "cpu_bomb.py", timeout=5)
        self.assertTrue(result.timed_out)

    def test_memory_bomb(self):
        """Excessive memory allocation should be killed by OOM."""
        result = run_plugin_script(
            PLUGIN_DIR, "memory_bomb.py", timeout=15, memory_limit="64m"
        )
        # Should either OOM kill or get MemoryError
        self.assertTrue(
            result.oom_killed
            or result.exit_code != 0
            or "BLOCKED" in result.stdout
        )

    def test_write_host_filesystem(self):
        """Writing to read-only filesystem should fail."""
        result = run_plugin_script(PLUGIN_DIR, "write_host.py", timeout=10)
        self.assertIn("BLOCKED", result.stdout)
        self.assertNotIn("FAIL", result.stdout)

if __name__ == "__main__":
    unittest.main()
