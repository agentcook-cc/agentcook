"""Chapter 25: one structured log line per request — enough to debug production."""

import json
import logging
import time
import uuid

logger = logging.getLogger("agentcook")


class RequestTracer:
    def __init__(self, session_id: str, user_id: str = ""):
        self.trace_id = uuid.uuid4().hex[:8]
        self.session_id = session_id
        self.user_id = user_id
        self.start_time = time.perf_counter()
        self.rounds = 0
        self.tools_called: list[dict] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.status = "ok"

    def add_usage(self, usage) -> None:
        if usage is not None:
            self.input_tokens += getattr(usage, "input_tokens", 0) or 0
            self.output_tokens += getattr(usage, "output_tokens", 0) or 0

    def log_tool_call(self, tool_name: str, latency_ms: int, success: bool) -> None:
        self.tools_called.append({"name": tool_name, "latency_ms": latency_ms, "success": success})

    def finish(self, status: str | None = None) -> dict:
        if status:
            self.status = status
        entry = {
            "event": "agent_run",
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "status": self.status,
            "total_ms": int((time.perf_counter() - self.start_time) * 1000),
            "rounds": self.rounds,
            "tools": self.tools_called,
            "tokens": {"input": self.input_tokens, "output": self.output_tokens},
        }
        logger.info(json.dumps(entry, ensure_ascii=False))
        return entry
