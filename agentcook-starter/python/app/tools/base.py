"""The tool contract: everything the LLM needs to know, plus how to run it."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Subclass, fill in the four members, register an instance. That's a tool.

    Subclasses usually set ``name`` / ``description`` / ``parameters`` as
    plain class attributes, which satisfies the abstract properties.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name the LLM calls it by."""

    @property
    @abstractmethod
    def description(self) -> str:
        """When to use the tool — written for the LLM, it decides call accuracy."""

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema of the arguments."""

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Do the work. Return JSON-serialisable data; raise or return {"error": ...} on failure."""

    # --- Mock mode -----------------------------------------------------------
    # The offline mock model (agent/mock_llm.py) has no real understanding, so
    # tools tell it when they are relevant. Real LLMs ignore these two members.

    #: Words in a user message that make the mock model call this tool.
    keywords: tuple[str, ...] = ()

    def mock_arguments(self, message: str) -> dict:
        """Arguments the mock model passes. Default: the message for each required string field."""
        props = self.parameters.get("properties", {})
        return {
            key: message for key in self.parameters.get("required", []) if props.get(key, {}).get("type") == "string"
        }

    def to_definition(self) -> dict:
        """The tool as the Anthropic Messages API expects it in ``tools=[...]``."""
        return {"name": self.name, "description": self.description, "input_schema": self.parameters}
