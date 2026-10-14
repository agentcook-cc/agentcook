"""Dependency-free token estimation.

The classic "4 characters per token" rule is tuned for English. For
Chinese / Japanese / Korean text it undercounts by roughly 4x — every
CJK ideograph is usually *at least* one token — which is how context
windows silently overflow on CJK-heavy traffic. This estimator counts
CJK code points individually and applies the 4-char rule to the rest.

Use a vendor tokenizer when you need exact numbers; use this when you
need a fast, conservative estimate for budgeting decisions.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from agentcook_core.types import Message

# Per-message framing overhead (role markers, separators) — the same
# ballpark OpenAI documents for ChatML.
MESSAGE_OVERHEAD_TOKENS = 4


def _is_cjk(cp: int) -> bool:
    return (
        0x3040 <= cp <= 0x30FF  # Hiragana + Katakana
        or 0x3400 <= cp <= 0x4DBF  # CJK Ext A
        or 0x4E00 <= cp <= 0x9FFF  # CJK Unified
        or 0xAC00 <= cp <= 0xD7AF  # Hangul
        or 0xF900 <= cp <= 0xFAFF  # CJK Compatibility
        or 0xFF00 <= cp <= 0xFFEF  # Full-width forms
        or 0x20000 <= cp <= 0x2FA1F  # CJK Ext B+
        or 0x3000 <= cp <= 0x303F  # CJK punctuation
    )


def estimate_tokens(text: str) -> int:
    """Conservative token estimate for mixed CJK / Latin text."""
    if not text:
        return 0
    cjk = 0
    other = 0
    for ch in text:
        if _is_cjk(ord(ch)):
            cjk += 1
        else:
            other += 1
    return cjk + (other + 3) // 4


def estimate_message_tokens(message: Message) -> int:
    total = MESSAGE_OVERHEAD_TOKENS + estimate_tokens(message.content)
    if message.tool_calls:
        for call in message.tool_calls:
            total += estimate_tokens(call.name)
            total += estimate_tokens(json.dumps(call.arguments, ensure_ascii=False))
    return total


def estimate_messages_tokens(messages: Iterable[Message]) -> int:
    return sum(estimate_message_tokens(m) for m in messages)


__all__ = [
    "MESSAGE_OVERHEAD_TOKENS",
    "estimate_message_tokens",
    "estimate_messages_tokens",
    "estimate_tokens",
]
