"""Locust performance — five user shapes covering monolith + swarm + gRPC.

Phase 4 Day 41 — Agent C extension. The Day 30 baseline (`JavaApiUser` +
`PythonSkillUser`) covered the pre-swarm monolith. Day 41 adds:

    - SwarmGatewayUser    — same flows but through Traefik gateway :80
    - GrpcChatUser        — direct gRPC client against Java :9090

Use `--tags <tag>` to filter; tags map onto the deployment topology:

    monolith   → JavaApiUser, PythonSkillUser
    swarm      → SwarmGatewayUser
    grpc       → GrpcChatUser

Examples:

    # Monolith baseline (Day 30 behaviour, pre-swarm)
    LOCUST_HOST=http://127.0.0.1:8080 \
      uv run locust -f tests/performance/locustfile.py \
        --headless -u 50 -r 5 -t 60s --tags monolith

    # Swarm via gateway (Phase 4 default)
    GATEWAY_BASE=http://127.0.0.1 \
      uv run locust -f tests/performance/locustfile.py \
        --headless -u 100 -r 10 -t 120s --tags swarm

    # gRPC slice
    GRPC_TARGET=127.0.0.1:9090 \
      uv run locust -f tests/performance/locustfile.py \
        --headless -u 20 -r 5 -t 60s --tags grpc

Phase 5 Day 50 ramps swarm 50 → 100 → 200 → 500 (see `k6/full-ramp.js`).
"""

from __future__ import annotations

import os
import random
import time
from typing import Any

from locust import FastHttpUser, User, between, tag, task

JAVA_BASE = os.environ.get("LOCUST_JAVA_BASE", "http://127.0.0.1:8080")
PYTHON_BASE = os.environ.get("LOCUST_PYTHON_BASE", "http://127.0.0.1:8000")
GATEWAY_BASE = os.environ.get("GATEWAY_BASE", "http://127.0.0.1")
GRPC_TARGET = os.environ.get("GRPC_TARGET", "127.0.0.1:9090")

SKILL_IDS = [
    "summarize-conversation",
    "extract-entities",
    "classify-intent",
]


@tag("monolith")
class JavaApiUser(FastHttpUser):
    """Drives Java-backed admin flows (auth + user list)."""

    host = JAVA_BASE
    wait_time = between(0.5, 2.0)
    access_token: str | None = None

    def on_start(self) -> None:
        # Dev-profile auth returns `dev-token-{username}` for any
        # non-empty creds; we don't need a unique user per locust user.
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": f"loaduser-{random.randint(1, 10_000)}", "password": "dev"},
            name="POST /api/v1/auth/login",
        )
        if resp.status_code == 200:
            body: dict[str, Any] = resp.json()
            self.access_token = body.get("accessToken") or body.get("access_token")

    @task(3)
    def list_users(self) -> None:
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        self.client.get(
            "/api/v1/users",
            headers=headers,
            name="GET /api/v1/users",
        )

    @task(1)
    def list_plugins(self) -> None:
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        self.client.get(
            "/api/v1/plugins",
            headers=headers,
            name="GET /api/v1/plugins",
        )


@tag("monolith")
class PythonSkillUser(FastHttpUser):
    """Drives Python-backed skill streaming (SSE).

    Hits the same FastAPI app on a separate host so locust counts the
    two surfaces independently (admin user vs end-user app).
    """

    host = PYTHON_BASE
    wait_time = between(1.0, 3.0)

    @task(2)
    def list_skills(self) -> None:
        self.client.get("/api/v1/skills", name="GET /api/v1/skills")

    @task(1)
    def stream_skill(self) -> None:
        skill_id = random.choice(SKILL_IDS)
        # SSE endpoints stream forever from the server's POV; we set
        # `stream=True` and drain the body so locust records the full
        # response time (10×500ms ≈ 5s in the mock implementation).
        with self.client.post(
            f"/api/v1/skills/{skill_id}/test/stream",
            json={"input": "load test ping"},
            name="POST /api/v1/skills/[id]/test/stream",
            stream=True,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"non-200: {resp.status_code}")
                return
            chunk_count = 0
            for line in resp.iter_lines():
                if line and line.startswith(b"data:"):
                    chunk_count += 1
            if chunk_count == 0:
                resp.failure("no SSE chunks received")
            else:
                resp.success()


# ---------------------------------------------------------------------------
# Phase 4 Day 41 — swarm + gRPC user shapes
# ---------------------------------------------------------------------------


@tag("swarm")
class SwarmGatewayUser(FastHttpUser):
    """Same flows as the monolith Users, but routed through Traefik :80.

    Latency here includes the Day 38-40 swarm split: gateway → service
    discovery (etcd) → Java/Python target. We expect a small p99 bump vs
    `JavaApiUser` direct hits — the diff size is what we care about.

    Routing assumption (per ``agentcook-swarm/gateway/dynamic/`` written
    by B Day 39):
        /api/v1/auth/**   → admin-bff (Java)
        /api/v1/users     → admin-bff
        /api/v1/skills    → agent-core (Python)
        /api/v1/chat/**   → agent-core (Python, SSE)
    """

    host = GATEWAY_BASE
    wait_time = between(0.5, 2.0)
    access_token: str | None = None

    def on_start(self) -> None:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": f"swarm-{random.randint(1, 10_000)}",
                "password": "dev",
            },
            name="POST /api/v1/auth/login (gateway)",
        )
        if resp.status_code == 200:
            body: dict[str, Any] = resp.json()
            self.access_token = body.get("accessToken") or body.get("access_token")

    @task(3)
    def list_users(self) -> None:
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        self.client.get(
            "/api/v1/users",
            headers=headers,
            name="GET /api/v1/users (gateway)",
        )

    @task(2)
    def list_skills(self) -> None:
        # Skills isn't auth-gated in the Phase 3 spec; Phase 4 keeps the
        # same surface — gateway just routes to agent-core.
        self.client.get("/api/v1/skills", name="GET /api/v1/skills (gateway)")

    @task(1)
    def chat_stream(self) -> None:
        """End-user chat — full SSE pipeline through gateway → agent-core."""
        headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
        with self.client.post(
            "/api/v1/chat/stream",
            json={
                "session_id": f"swarm-{random.randint(1, 10_000)}",
                "input": "swarm load test",
            },
            headers=headers,
            name="POST /api/v1/chat/stream (gateway)",
            stream=True,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"non-200: {resp.status_code}")
                return
            chunk_count = 0
            for line in resp.iter_lines():
                if line and line.startswith(b"data:"):
                    chunk_count += 1
                if chunk_count >= 3:
                    # Don't drain the full stream under 500u — we just want
                    # to confirm the SSE pipe opened and pushed data.
                    break
            if chunk_count == 0:
                resp.failure("no SSE chunks received")
            else:
                resp.success()


@tag("grpc")
class GrpcChatUser(User):
    """Direct gRPC client against the Java admin-bff GrpcChatService.

    Uses a `User` (not `FastHttpUser`) so we own the channel lifecycle
    explicitly and can reuse the channel across iterations — opening a
    new gRPC channel per iteration would dominate the measurement.

    We import grpcio lazily so a missing or stale stub doesn't break
    `--tags monolith` / `--tags swarm` runs.
    """

    wait_time = between(1.0, 2.0)
    _channel = None
    _stub = None

    def on_start(self) -> None:
        try:
            import grpc

            self._channel = grpc.insecure_channel(GRPC_TARGET)
            # The chat service stub lives in agentcook-swarm/services/agent-core
            # generated from the proto file. We probe via the channel ready
            # check rather than importing a stub here, since proto regen
            # may be in flight in the parent project.
            grpc.channel_ready_future(self._channel).result(timeout=5)
        except Exception as exc:
            self.environment.runner.quit()  # type: ignore[union-attr]
            raise RuntimeError(
                f"gRPC channel to {GRPC_TARGET} not ready: {exc}. "
                "Run swarm services or skip with --tags swarm/monolith."
            ) from exc

    def on_stop(self) -> None:
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass

    @task
    def grpc_chat_unary(self) -> None:
        """gRPC unary ping.

        We deliberately do NOT marshal the real chat proto here — the
        proto module location is still in flux per A's Day 38-40 swarm
        commit. Instead we measure channel + stream open latency via
        a `connectivity_state` poll (a 1-RTT round trip in practice).
        Phase 5 Day 50 will wire the real `Chat.Stream` once the proto
        module path stabilises.
        """
        import grpc

        start = time.time()
        try:
            state = self._channel._channel.check_connectivity_state(True)  # type: ignore[union-attr]
            ok = state in (grpc.ChannelConnectivity.READY, 4)  # READY enum or numeric fallback
        except Exception:
            ok = False
        elapsed_ms = (time.time() - start) * 1000

        self.environment.events.request.fire(
            request_type="GRPC",
            name="grpc:Chat.connectivity_probe",
            response_time=elapsed_ms,
            response_length=0,
            exception=None if ok else RuntimeError("channel not ready"),
            context={},
        )
