"""Demo: cross-package import verification.

Run: uv run python scripts/demo_cross_import.py

Verifies that ``agentcook-providers`` can import from ``agentcook-core`` and
that the bundled :class:`EchoProvider` satisfies :class:`LLMProviderProtocol`.
"""

from __future__ import annotations

import asyncio

from agentcook_core import LLMProviderProtocol, Message
from agentcook_core import __version__ as core_version
from agentcook_providers.echo_provider import EchoProvider


async def main() -> None:
    print(f"agentcook-core version: {core_version}")

    provider = EchoProvider(prefix="Demo")
    print(f"EchoProvider satisfies LLMProviderProtocol: {isinstance(provider, LLMProviderProtocol)}")

    response = await provider.chat([Message(role="user", content="Hello from cross-package import!")])
    print(f"chat() result: {response.message.content}")

    print("\n✅ Cross-package import works!")


if __name__ == "__main__":
    asyncio.run(main())
