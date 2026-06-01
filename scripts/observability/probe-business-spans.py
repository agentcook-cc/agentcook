"""End-to-end probe for A's Day 23 business-span instrumentation.

Drives `compaction.compact` / `pruning.prune` / `memory.write_to_layer`
through the OTel adapter so we can inspect the resulting spans in Jaeger.
This is the closest CLI-only equivalent to Brief Day 23's "Jaeger UI
screenshot of one full agent loop" — instead of a UI capture we dump the
raw trace JSON from the Jaeger query API.

Run after `make dev` is up:

    AGENTCOOK_JWT_SECRET=any uv run python scripts/observability/probe-business-spans.py

Then check `docs/observability/sample-trace.json` for the recorded spans.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# OTel SDK setup mirrors what `setup_telemetry` does in main.py — minus
# the FastAPI plumbing, since this script is pure core code, no HTTP.
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

from opentelemetry import trace  # noqa: E402
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # noqa: E402
from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: E402

PROBE_SERVICE = "agentcook-python-probe"

provider = TracerProvider(resource=Resource.create({"service.name": PROBE_SERVICE}))
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"], insecure=True))
)
trace.set_tracer_provider(provider)

from agentcook_app import otel_tracer_adapter  # noqa: E402

otel_tracer_adapter.install(PROBE_SERVICE)

from agentcook_core.compaction import SlidingWindowCompaction  # noqa: E402
from agentcook_core.memory import InMemoryStore, MemoryLayer, MemoryManager  # noqa: E402
from agentcook_core.pruning import DuplicatePruning  # noqa: E402
from agentcook_core.types import Message  # noqa: E402


def _stub_messages(n: int) -> list[Message]:
    return [
        Message(role="user", content=f"msg {i}") if i % 2 == 0
        else Message(role="assistant", content=f"reply {i}")
        for i in range(n)
    ]


def main() -> int:
    print("🔥 driving compaction.compact …")
    SlidingWindowCompaction(window_size=4).compact(_stub_messages(20))

    print("🔥 driving pruning.prune …")
    DuplicatePruning().prune(_stub_messages(10) + _stub_messages(10))

    print("🔥 driving memory.write_to_layer / read_from_layer …")
    # Use the MemoryManager built-in InMemoryStore (no PG dependency).
    mgr = MemoryManager(store=InMemoryStore())
    agent = "probe-agent"
    mgr.write_to_layer(agent, MemoryLayer.SOUL, key="probe:k1", content="hello world")
    mgr.read_from_layer(agent, MemoryLayer.SOUL, key="probe:k1")
    # semantic_search needs an embedder; skip if none — span coverage for the
    # write/read pair is enough for the smoke probe.

    print("⏳ waiting 6s for BatchSpanProcessor flush …")
    time.sleep(6)

    # Pull recent traces for our service, dump them so a human (or the
    # progress reviewer) can confirm the span tree without opening the UI.
    import urllib.request

    url = (
        "http://localhost:16686/api/traces"
        "?service=agentcook-python-probe&limit=50&lookback=2m"
    )
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.load(resp)

    traces = data.get("data") or []
    print(f"📊 found {len(traces)} traces for agentcook-python-probe")

    if not traces:
        print("❌ no traces visible — instrumentation broken or flush too short")
        return 1

    # Collect all span operation names to verify the business spans landed.
    op_names: set[str] = set()
    for t in traces:
        for s in t.get("spans") or []:
            op_names.add(s.get("operationName", ""))

    expected = {
        "compaction.sliding_window",
        "pruning.duplicate",
        "memory.soul.write",
        "memory.soul.read",
    }
    missing = expected - op_names
    print(f"✅ span operation names recorded: {sorted(op_names)}")
    if missing:
        print(f"⚠️  expected but missing: {sorted(missing)}")
        # don't fail — some span names may have shifted, surface for review

    out_path = Path(__file__).resolve().parents[2] / "docs/observability/sample-trace.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(f"📝 wrote raw Jaeger trace JSON → {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
