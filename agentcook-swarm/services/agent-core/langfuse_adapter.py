"""Langfuse SDK adapter — bridges agentcook_core.LangfuseHook Protocol.

This is the application-layer side of the same pattern OTel uses
(``agentcook_app.otel_tracer_adapter``):

- ``agentcook_core.langfuse_hook`` defines a stdlib-only Protocol.
- This module imports the real ``langfuse`` SDK and implements the
  Protocol on top of it.
- ``install(...)`` registers an adapter into core via
  ``set_langfuse_hook(LangfuseAdapter(...))``.

Wire flow::

    setup_telemetry(app)               # observability.py
        └─ install_langfuse()          # this module — bridges into core
            └─ set_langfuse_hook(LangfuseAdapter(client))

After install, ``model_router.select()`` and ``OpenAIProvider.chat()``
emit Langfuse ``generation`` records without ever importing the SDK
themselves.

Environment variables read:

- ``LANGFUSE_SECRET_KEY``  — required to install (else NoOp stays)
- ``LANGFUSE_PUBLIC_KEY``  — required
- ``LANGFUSE_HOST``        — defaults to https://cloud.langfuse.com
- ``LANGFUSE_ENABLED``     — set to ``false`` to force NoOp even with keys
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

from agentcook_core.langfuse_hook import (
    NoOpHook,
    set_langfuse_hook,
)

logger = logging.getLogger(__name__)


class LangfuseAdapter:
    """Implements ``agentcook_core.LangfuseHook`` over the langfuse SDK.

    Each ``observe_model_call`` becomes a Langfuse ``generation``
    record. SDK exceptions are swallowed — telemetry must never break
    the caller (model_router / provider).
    """

    __slots__ = ("_client",)

    def __init__(self, client: Any) -> None:
        # ``client`` is a ``langfuse.Langfuse`` instance — typed as Any
        # so this file can be imported even before the SDK ships.
        self._client = client

    def observe_model_call(
        self,
        *,
        model: str,
        provider: str,
        prompt: str | list | None = None,
        completion: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            usage = {
                "input": prompt_tokens,
                "output": completion_tokens,
                "total": prompt_tokens + completion_tokens,
                "unit": "TOKENS",
            }
            # Langfuse-style flat metadata: include provider + our event
            # marker + any user-supplied extras.
            md = {
                "provider": provider,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                **dict(metadata or {}),
            }
            self._client.generation(
                name=f"{provider}:{model}",
                model=model,
                input=prompt,
                output=completion,
                usage=usage,
                metadata=md,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Langfuse generation() failed", exc_info=True)

    def flush(self) -> None:
        try:
            self._client.flush()
        except Exception:  # noqa: BLE001
            logger.debug("Langfuse flush() failed", exc_info=True)


def install() -> bool:
    """Construct + install LangfuseAdapter if env vars + SDK are present.

    Returns True on real install, False on fallback to NoOp. Idempotent
    — calling twice swaps the hook (cheap).
    """
    if os.getenv("LANGFUSE_ENABLED", "true").lower() == "false":
        logger.info("LANGFUSE_ENABLED=false — staying in NoOp mode")
        set_langfuse_hook(NoOpHook())
        return False

    secret = os.getenv("LANGFUSE_SECRET_KEY")
    public = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret or not public:
        logger.info("LANGFUSE_{SECRET,PUBLIC}_KEY unset — NoOp mode")
        set_langfuse_hook(NoOpHook())
        return False

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.info("langfuse SDK not installed — NoOp mode")
        set_langfuse_hook(NoOpHook())
        return False

    try:
        client = Langfuse(secret_key=secret, public_key=public, host=host)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse client init failed: %s — NoOp mode", exc)
        set_langfuse_hook(NoOpHook())
        return False

    set_langfuse_hook(LangfuseAdapter(client))
    logger.info("LangfuseAdapter installed (host=%s)", host)
    return True


__all__ = ["LangfuseAdapter", "install"]
