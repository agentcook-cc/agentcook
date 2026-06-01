# Plugin Docker Sandbox — penetration test report

Owner: Agent C. Phase 4 Day 42 — formal write-up of the 6 attack vectors
already exercised by `poc/plugin-sandbox/test_attack_vectors.py` (Phase 0
Day 4 by track-f), plus three new vectors added Day 42.

> The sandbox runs each plugin script inside a one-shot container with:
>
> - `--network=none` (no outbound or inbound networking)
> - `--read-only` (immutable rootfs, with `/tmp` as the only writable tmpfs)
> - `--cap-drop=ALL --security-opt=no-new-privileges`
> - `--memory=512m --memory-swap=512m` (no swap escape)
> - `--cpus=0.5 --pids-limit=128`
> - timeout enforced by the host (`subprocess.run(timeout=...)`)
>
> Source: `poc/plugin-sandbox/sandbox_runner.py` + `Dockerfile`.

> Status legend: ✅ blocked · 🟡 partially blocked · 🔴 not blocked

---

## A. Original 5 vectors (Phase 0 Day 4 — verified Day 42)

### 1. Read host filesystem (`/etc/passwd` and friends)

**What we tried.** A plugin reads `/etc/passwd` expecting to enumerate
host users.

**Test.** `poc/plugin-sandbox/test_attack_vectors.py::test_read_host_passwd`
runs `read_passwd.py` inside the sandbox.

**Result.** ✅ Blocked. The container has its own `/etc/passwd` with a
single non-privileged `sandbox` user. The host's `root:x:0:0:root` line
is absent.

**Why it works.** Docker bind-mounts no host paths into the sandbox;
the rootfs comes entirely from the image.

### 2. Network egress (curl an external URL)

**Test.** `network_escape.py` issues `curl https://example.com/`.

**Result.** ✅ Blocked. With `--network=none`, the container has only
`lo`. `curl` returns "Could not resolve host", and the script's
guard prints `BLOCKED`.

**Why it works.** Docker creates no network namespace bridge; DNS is
unreachable.

### 3. CPU exhaustion (infinite loop)

**Test.** `cpu_bomb.py` enters `while True: pass`.

**Result.** ✅ Killed by host timeout (5s). The script is reaped by
`subprocess.terminate()` after the configured wallclock budget.

**Note.** `--cpus=0.5` reduces blast radius on the host even before
the timeout fires — neighbours still get half a core.

### 4. Memory bomb

**Test.** `memory_bomb.py` allocates a 1 GiB list under a `--memory=64m`
limit.

**Result.** ✅ Killed by Linux OOM. The runner detects `oom_killed=True`
or non-zero exit. Either signal proves containment.

### 5. Write to host filesystem

**Test.** `write_host.py` opens `/etc/sandbox-attack` for write.

**Result.** ✅ Blocked. The rootfs is mounted `--read-only`, so the
write fails with `EROFS`. `/tmp` is the only writable mount, and it's
a tmpfs scoped to the container's lifetime.

---

## B. New vectors added Day 42

### 6. Capability bypass (try to mount, change uid, ptrace)

**What we tried.** Inside the plugin, `os.system("mount -t proc proc /proc")`
and `os.setuid(0)`.

**Test.** Day 42 ad-hoc — no automated test yet. Reproduce:

```bash
docker run --rm --network=none --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges agentcook-plugin-sandbox \
  python -c "import os; os.setuid(0)"
```

**Result.** ✅ Blocked. `setuid` returns `PermissionError` (EPERM);
`mount` returns "operation not permitted". `--cap-drop=ALL` removes
`CAP_SYS_ADMIN` and `CAP_SETUID` from the container.

**Fix / follow-up.** 📅 Phase 5 Day 51: add a regression test
(`test_setuid_blocked`, `test_mount_blocked`).

### 7. Process / fork bomb

**What we tried.** Recursive `os.fork()` until the kernel runs out of
PIDs.

**Test.** Day 42 ad-hoc:

```bash
docker run --rm --pids-limit=128 agentcook-plugin-sandbox \
  python -c "
import os
for _ in range(10000):
    if os.fork() == 0: pass
"
```

**Result.** ✅ Blocked. After ~128 children, `fork()` raises
`BlockingIOError: [Errno 11] Resource temporarily unavailable`. Host
load stays normal.

**Fix / follow-up.** 📅 Phase 5 Day 51: regression test +
`--pids-limit=64` (more headroom than we need; 128 is generous for a
plugin).

### 8. SSRF via DNS rebinding (network=none renders this moot)

**What we tried.** Plugin asks the network for `localhost.attacker.com`
which resolves to a host-local IP.

**Result.** ✅ Blocked by `--network=none`. The plugin can't even
resolve a hostname, let alone contact one.

**Note.** If we ever switch to `--network=plugin-net` (a custom bridge
without internet egress), DNS rebinding becomes possible and we'd add
a CoreDNS allowlist. Today we don't.

### 9. tmpfs exhaustion

**What we tried.** Write 1 GiB to `/tmp` to fill the writable layer.

**Result.** 🟡 Partial. `/tmp` is a tmpfs but has no explicit size
cap. A plugin can fill the host's RAM via `/tmp` until OOM kills it.

**Fix / follow-up.** 🔴 Open. Add `--tmpfs /tmp:size=64m` to
`sandbox_runner.py`. Owner: A (sandbox owner from Phase 0 Day 4),
Phase 5 Day 51.

---

## Summary

| Vector | Status | Test |
|---|---|---|
| 1. Read host fs | ✅ blocked | `test_read_host_passwd` |
| 2. Network egress | ✅ blocked | `test_network_escape` |
| 3. CPU exhaustion | ✅ blocked | `test_cpu_bomb` |
| 4. Memory bomb | ✅ blocked | `test_memory_bomb` |
| 5. Write host fs | ✅ blocked | `test_write_host_filesystem` |
| 6. Capability bypass | ✅ blocked | manual; auto Day 51 |
| 7. Fork bomb | ✅ blocked | manual; auto Day 51 |
| 8. SSRF via DNS | ✅ blocked (by 2) | covered by 2 |
| 9. tmpfs exhaustion | 🟡 partial | open: add `tmpfs size=64m` |

**One open finding (#9 tmpfs)** — tracked in `owasp-checklist.md` A10
SSRF section as a follow-up. Owner A, Phase 5 Day 51.

Re-run before each release tag.
