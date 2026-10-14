"""Chapter 25: a cheap first filter for obvious prompt-injection attempts.

This is not a security boundary — the real protections are the safety rules
in the system prompt and read-only tools. It just stops the laziest attacks
before they cost a model call.
"""

import re

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"忽略.{0,10}(之前|上面|以上|所有|全部).{0,10}(指令|规则|限制|提示)",
        r"(输出|打印|显示|告诉我|重复|泄露).{0,10}(system\s*prompt|系统提示|系统指令|你的指令|你的提示词)",
        r"(ignore|disregard|forget).{0,20}(previous|above|prior|all|your).{0,20}(instructions|rules|prompts?)",
        r"(reveal|print|show|repeat|leak).{0,20}(system\s*prompt|your\s+(instructions|prompt))",
    )
]

REFUSAL = "我只能帮你解决业务相关的问题，请换个方式描述你的需求 😊"


def check_injection(message: str) -> bool:
    return any(pattern.search(message) for pattern in INJECTION_PATTERNS)
