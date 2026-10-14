"""Chat orchestration — one user turn, end to end.

``ChatService.start_turn`` turns a validated chat request into a running
agent loop:

1. resolve the agent spec and the caller's *agent instance* (one per
   ``(agent, user)`` pair — that is where identity / soul / long-term
   memory live, ADR-011);
2. claim the session (ownership is enforced by the conversation store);
3. pick the model: per-agent override → ADR-018 quota routing → default;
4. assemble tools (agent toolkits + request ``plugin_ids`` + skills +
   memory + delegate sub-agents) and a cache-friendly system prompt;
5. replay the transcript and start the run under the :class:`RunManager`.

The run task converts :data:`AgentEvent` values into wire frames (see
:func:`frame_for`) and persists the new messages when it finishes — even
if the client has disconnected.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from agentcook_core import (
    Agent,
    AgentEvent,
    AgentRunner,
    AgentTool,
    IdentityCard,
    Message,
    RunCompleted,
    RunContext,
    RunFailed,
    RunStarted,
    TextDelta,
    ToolCallCompleted,
    ToolCallStarted,
    ToolPolicy,
    ToolProtocol,
)
from agentcook_core.builtin_tools import make_load_skill_tool
from agentcook_core.prompts import build_agent_system_prompt, render_skill_catalog
from agentcook_core.skill_loader import SkillRegistry

from agentcook_app.agents import AgentSpec
from agentcook_app.container import AppContainer
from agentcook_app.metrics import AgentMetricsHooks
from agentcook_app.runs import RunHandle
from agentcook_app.security import UserContext
from agentcook_app.services import SoulNotInitializedError
from agentcook_app.toolkits import make_memory_tools

logger = logging.getLogger(__name__)

MEMORY_MIN_SCORE = 0.15
_BACKGROUND: set[asyncio.Task[None]] = set()
MAX_FRAME_OUTPUT_CHARS = 4_000


class ModelUnavailableError(RuntimeError):
    """The requested / configured model provider cannot be constructed."""

    def __init__(self, spec: str, reason: str, *, client_error: bool) -> None:
        super().__init__(f"model {spec!r} is unavailable: {reason}")
        self.spec = spec
        self.reason = reason
        self.client_error = client_error


def normalize_model_spec(value: str, default_spec: str) -> str:
    """Interpret a request ``model`` override.

    ``qwen:qwen-plus`` / ``mock`` / ``qwen,zhipu`` are provider specs and
    pass through; a bare model name (``qwen-plus``) is applied to the
    default provider (``qwen`` → ``qwen:qwen-plus``).
    """
    from agentcook_providers import SUPPORTED_PROVIDERS

    value = value.strip()
    head = value.split(",")[0].split(":")[0].strip().lower()
    if ":" in value or "," in value or head in SUPPORTED_PROVIDERS:
        return value
    default_provider = default_spec.split(",")[0].split(":")[0].strip()
    return f"{default_provider}:{value}"


class AgentNotAvailableError(LookupError):
    def __init__(self, name: str, available: Sequence[str]) -> None:
        super().__init__(f"unknown agent {name!r}; available: {', '.join(available)}")
        self.name = name
        self.available = list(available)


@dataclass(frozen=True, slots=True)
class ChatTurn:
    session_id: str
    message: str
    agent: str | None = None
    plugin_ids: tuple[str, ...] = ()
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(slots=True)
class PreparedRun:
    agent: Agent
    spec: AgentSpec
    runner: AgentRunner
    system_prompt: str
    history: list[Message]
    context: RunContext
    model_label: str
    provider_label: str
    quota_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


def agent_instance_id(agent_name: str, user_id: str) -> str:
    """Stable per-(agent, user) instance id; safe for URL paths."""
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
    return f"{agent_name}-{digest}"


def _truncate(text: str | None, limit: int = MAX_FRAME_OUTPUT_CHARS) -> str | None:
    if text is None or len(text) <= limit:
        return text
    return text[:limit] + f"… [{len(text) - limit} more characters]"


def frame_for(event: AgentEvent, *, run: PreparedRun, session_id: str) -> dict[str, Any] | None:
    """Map an agent event onto the chat SSE wire frame.

    Every frame keeps the v1 fields (``role`` / ``content`` / ``done``)
    so older clients that only concatenate ``content`` keep working; the
    ``type`` field and the ``tool_call`` object carry the richer protocol.
    """
    if isinstance(event, RunStarted):
        return {
            "type": "start",
            "role": "assistant",
            "content": "",
            "done": False,
            "session_id": session_id,
            "run_id": event.run_id,
            "metadata": {
                "agent": run.spec.name,
                "agent_title": run.spec.title,
                "model": run.model_label,
                "provider": run.provider_label,
                "warnings": run.warnings,
            },
        }
    if isinstance(event, TextDelta):
        return {"type": "delta", "role": "assistant", "content": event.text, "done": False}
    if isinstance(event, ToolCallStarted):
        call = {
            "id": event.call.id,
            "name": event.call.name,
            "arguments": event.call.arguments,
            "status": "running",
            "turn": event.turn,
        }
        return {
            "type": "tool_call",
            "role": "assistant",
            "content": "",
            "done": False,
            "tool_call": call,
            "tool_calls": [call],
        }
    if isinstance(event, ToolCallCompleted):
        call = {
            "id": event.call.id,
            "name": event.call.name,
            "arguments": event.call.arguments,
            "status": "success" if event.result.success else "error",
            "output": _truncate(event.output),
            "error": event.result.error,
            "duration_ms": round(event.duration_ms, 1),
            "turn": event.turn,
        }
        return {
            "type": "tool_result",
            "role": "tool",
            "content": "",
            "done": False,
            "tool_call": call,
            "tool_calls": [call],
        }
    if isinstance(event, RunCompleted):
        return {
            "type": "done",
            "role": "assistant",
            "content": "",
            "done": True,
            "run_id": event.run_id,
            "metadata": {
                **_run_metadata(run, event.usage, event.turns, event.duration_ms),
                "request_id": event.run_id,
                "finish_reason": event.finish_reason,
                "delegations": run.context.state.get("delegations", []),
            },
        }
    if isinstance(event, RunFailed):
        return {
            "type": "error",
            "role": "assistant",
            "content": "",
            "done": True,
            "run_id": event.run_id,
            "error": f"{event.error_type}: {event.error}",
            "metadata": {
                **_run_metadata(run, event.usage, event.turns, event.duration_ms),
                "request_id": event.run_id,
                "finish_reason": "error",
            },
        }
    return None


def _run_metadata(run: PreparedRun, usage: Any, turns: int, duration_ms: float) -> dict[str, Any]:
    return {
        "agent": run.spec.name,
        "model": run.model_label,
        "provider": run.provider_label,
        "usage": {
            "input_tokens": usage.input,
            "output_tokens": usage.output,
            "cached_tokens": usage.cached,
            "total_tokens": usage.total,
        },
        "turns": turns,
        "duration_ms": round(duration_ms, 1),
        "source": "mock" if run.provider_label in ("MockProvider", "EchoProvider") else "provider",
        **({"quota": run.quota_reason} if run.quota_reason else {}),
    }


def _history_for_model(messages: Sequence[Message]) -> list[Message]:
    """Drop persisted failure placeholders that carry no content."""
    return [
        m
        for m in messages
        if not (
            m.role == "assistant" and not m.content and not m.tool_calls and m.metadata.get("error")
        )
    ]


class ChatService:
    def __init__(self, container: AppContainer) -> None:
        self._c = container

    # -- preparation ---------------------------------------------------

    async def prepare(self, user: UserContext, turn: ChatTurn) -> PreparedRun:
        c = self._c
        spec = c.agents.get(turn.agent)
        if spec is None:
            raise AgentNotAvailableError(turn.agent or "", [a.name for a in c.agents.list()])
        warnings: list[str] = []

        # Model selection: request override (non-production only) → agent
        # spec override → quota routing → configured default.
        provider_spec: str | None = None
        quota_reason: str | None = None
        from_request = False
        if turn.model and not c.settings.is_production:
            provider_spec = normalize_model_spec(turn.model, c.settings.llm_provider)
            from_request = True
        elif spec.model:
            provider_spec = spec.model
        elif c.settings.quota_enabled and not user.anonymous:
            decision = await self._resolve_quota(user)
            if decision is not None:
                provider_spec = (
                    f"{decision.provider}:{decision.model}" if decision.model else decision.provider
                )
                quota_reason = decision.reason
        try:
            provider = c.provider_for(provider_spec)
        except Exception as exc:  # unknown provider, missing SDK extra, missing API key …
            logger.warning("cannot build provider %r: %s", provider_spec, exc)
            raise ModelUnavailableError(
                provider_spec or c.settings.llm_provider,
                f"{type(exc).__name__}: {exc}"[:300],
                client_error=from_request,
            ) from exc

        instance_id = agent_instance_id(spec.name, user.user_id)
        card = await c.runtime.ensure_agent(
            instance_id,
            IdentityCard(
                name=spec.title,
                role=spec.description or spec.name,
                created_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                metadata={"agent": spec.name},
            ),
            user_id=user.user_id,
        )
        try:
            soul = (await c.runtime.get_soul_latest(instance_id)).config
        except SoulNotInitializedError:
            soul = None

        memories: list[str] = []
        if spec.memory:
            try:
                recall = await c.runtime.search_memory(instance_id, turn.message, top_k=3)
                memories = [h.content for h in recall.hits if h.score >= MEMORY_MIN_SCORE]
            except Exception:
                logger.warning("memory recall failed for %s", instance_id, exc_info=True)

        tools = await self._tools_for(spec, turn, instance_id, warnings)
        skills = self._skills_for(spec)
        if skills:
            tools.append(make_load_skill_tool(skills))

        runner = self._runner(provider)
        delegate_tools = self._delegate_tools(spec, runner)
        tools.extend(delegate_tools)

        system_prompt = build_agent_system_prompt(
            instructions=spec.instructions,
            identity=card,
            soul=soul,
            skills=[e.manifest for e in skills.list_skills()] if skills else (),
            memories=memories,
        )
        agent = Agent(
            name=spec.name,
            instructions=spec.instructions,
            description=spec.description,
            tools=tuple(_dedupe(tools)),
            max_turns=spec.max_turns or c.settings.max_turns,
            tool_timeout=c.settings.tool_timeout,
            temperature=turn.temperature if turn.temperature is not None else spec.temperature,
            max_tokens=turn.max_tokens or spec.max_tokens,
        )
        history = await c.conversations.load_messages(
            turn.session_id, user_id=user.user_id, limit=c.settings.history_limit
        )
        run_id = f"run_{uuid.uuid4().hex[:16]}"
        context = RunContext(
            run_id=run_id,
            agent_name=spec.name,
            session_id=turn.session_id,
            user_id=user.user_id,
            metadata={"agent_instance": instance_id},
        )
        return PreparedRun(
            agent=agent,
            spec=spec,
            runner=runner,
            system_prompt=system_prompt,
            history=_history_for_model(history),
            context=context,
            model_label=provider.model_name,
            provider_label=type(provider).__name__,
            quota_reason=quota_reason,
            warnings=warnings,
        )

    def _runner(self, provider: Any) -> AgentRunner:
        hooks = [AgentMetricsHooks(provider.model_name)]
        if self._c.settings.disabled_tools:
            hooks.append(ToolPolicy(deny=self._c.settings.disabled_tools))
        return AgentRunner(provider, hooks=hooks)

    async def _tools_for(
        self, spec: AgentSpec, turn: ChatTurn, instance_id: str, warnings: list[str]
    ) -> list[ToolProtocol]:
        c = self._c
        kit_ids = list(dict.fromkeys([*spec.toolkits, *turn.plugin_ids]))
        tools, unknown = c.toolkits.resolve(kit_ids)
        if unknown:
            warnings.append(f"ignored unknown plugin/toolkit id(s): {', '.join(unknown)}")
        if spec.memory:
            tools.extend(make_memory_tools(c.runtime, instance_id))
        return tools

    def _skills_for(self, spec: AgentSpec) -> SkillRegistry | None:
        registry = self._c.skills
        if spec.skills is None:
            return registry if len(registry) else None
        if not spec.skills:
            return None
        subset = SkillRegistry()
        for name in spec.skills:
            entry = registry.get(name)
            if entry is not None:
                subset.register(entry)
        return subset if len(subset) else None

    def _delegate_tools(self, spec: AgentSpec, runner: AgentRunner) -> list[ToolProtocol]:
        tools: list[ToolProtocol] = []
        for name in spec.delegates:
            sub_spec = self._c.agents.get(name)
            if sub_spec is None:
                continue
            sub_tools, _ = self._c.toolkits.resolve(sub_spec.toolkits)
            skills = self._skills_for(sub_spec)
            if skills:
                sub_tools.append(make_load_skill_tool(skills))
            instructions = sub_spec.instructions
            if skills:
                catalog = render_skill_catalog([e.manifest for e in skills.list_skills()])
                instructions = f"{instructions}\n\n## Skills\n{catalog}"
            sub_agent = Agent(
                name=sub_spec.name,
                description=sub_spec.description,
                instructions=build_agent_system_prompt(instructions=instructions),
                tools=tuple(_dedupe(sub_tools)),
                max_turns=sub_spec.max_turns or self._c.settings.max_turns,
                tool_timeout=self._c.settings.tool_timeout,
                temperature=sub_spec.temperature,
            )
            tools.append(AgentTool(sub_agent, runner, max_depth=1))
        return tools

    async def _resolve_quota(self, user: UserContext) -> Any:
        from agentcook_app.middleware.quota import QuotaResolver

        resolver = QuotaResolver(java_quota_url=f"{self._c.settings.java_base_url}/api/v1/quota")
        try:
            return await resolver.resolve(user.user_id, bearer_token=user.token)
        except Exception:
            logger.warning("quota resolution failed; using default provider", exc_info=True)
            return None

    # -- execution -----------------------------------------------------

    async def start_turn(self, user: UserContext, turn: ChatTurn) -> RunHandle:
        c = self._c
        spec = c.agents.get(turn.agent)
        if spec is None:
            raise AgentNotAvailableError(turn.agent or "", [a.name for a in c.agents.list()])
        busy = c.runs.active_for_session(turn.session_id)
        if busy is not None and busy.user_id == user.user_id:
            from agentcook_app.runs import SessionBusyError

            raise SessionBusyError(turn.session_id, busy.run_id)
        await c.conversations.ensure_session(
            turn.session_id,
            user_id=user.user_id,
            agent=spec.name,
            title=turn.message,
        )
        prepared = await self.prepare(user, turn)

        async def body(handle: RunHandle) -> None:
            await self._drive(handle, prepared, user, turn)

        return c.runs.start(
            run_id=prepared.context.run_id,
            user_id=user.user_id,
            session_id=turn.session_id,
            agent=prepared.spec.name,
            body=body,
        )

    async def _drive(
        self, handle: RunHandle, run: PreparedRun, user: UserContext, turn: ChatTurn
    ) -> None:
        user_message = Message(role="user", content=turn.message)
        text_so_far: list[str] = []
        outcome: RunCompleted | RunFailed | None = None
        try:
            async for event in run.runner.run_stream(
                run.agent,
                user_message,
                history=run.history,
                context=run.context,
                system_prompt=run.system_prompt,
            ):
                if isinstance(event, TextDelta):
                    text_so_far.append(event.text)
                if isinstance(event, (RunCompleted, RunFailed)):
                    outcome = event
                    await self._persist(turn, user, run, event)
                frame = frame_for(event, run=run, session_id=turn.session_id)
                if frame is not None:
                    handle.emit(frame)
        except asyncio.CancelledError:
            if outcome is None:
                await self._persist_cancelled(turn, user, run, user_message, "".join(text_so_far))
                handle.emit(
                    {
                        "type": "done",
                        "role": "assistant",
                        "content": "",
                        "done": True,
                        "run_id": run.context.run_id,
                        "metadata": {
                            "agent": run.spec.name,
                            "model": run.model_label,
                            "finish_reason": "cancelled",
                            "request_id": run.context.run_id,
                        },
                    }
                )
            handle.status = "cancelled"
            return
        if isinstance(outcome, RunCompleted) and run.quota_reason == "within_quota":
            task = asyncio.create_task(self._consume_quota(user))
            _BACKGROUND.add(task)
            task.add_done_callback(_BACKGROUND.discard)

    async def _persist(
        self, turn: ChatTurn, user: UserContext, run: PreparedRun, outcome: RunCompleted | RunFailed
    ) -> None:
        messages = list(outcome.new_messages)
        meta = {"run_id": outcome.run_id, "model": run.model_label, "agent": run.spec.name}
        if isinstance(outcome, RunCompleted) and messages and messages[-1].role == "assistant":
            final = messages[-1]
            messages[-1] = dataclasses.replace(
                final,
                metadata={
                    **final.metadata,
                    **meta,
                    "finish_reason": outcome.finish_reason,
                    "usage": {
                        "input_tokens": outcome.usage.input,
                        "output_tokens": outcome.usage.output,
                    },
                },
            )
        if isinstance(outcome, RunFailed):
            messages.append(
                Message(
                    role="assistant",
                    content="",
                    metadata={**meta, "error": f"{outcome.error_type}: {outcome.error}"},
                )
            )
        try:
            await self._c.conversations.append_messages(turn.session_id, messages)
        except Exception:
            logger.exception("failed to persist transcript for session %s", turn.session_id)
        delegations = run.context.state.get("delegations")
        if delegations:
            self._c.delegations.record(
                delegations, session_id=turn.session_id, user_id=user.user_id
            )

    async def _persist_cancelled(
        self,
        turn: ChatTurn,
        user: UserContext,
        run: PreparedRun,
        user_message: Message,
        partial: str,
    ) -> None:
        messages = [
            user_message,
            Message(
                role="assistant",
                content=partial,
                metadata={
                    "run_id": run.context.run_id,
                    "agent": run.spec.name,
                    "model": run.model_label,
                    "finish_reason": "cancelled",
                    **({} if partial else {"error": "cancelled before any output"}),
                },
            ),
        ]
        try:
            await asyncio.shield(self._c.conversations.append_messages(turn.session_id, messages))
        except Exception:
            logger.exception("failed to persist cancelled run for session %s", turn.session_id)

    async def _consume_quota(self, user: UserContext) -> None:
        url = f"{self._c.settings.java_base_url}/api/v1/quota/consume"
        headers = {"Authorization": f"Bearer {user.token}"} if user.token else {}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(url, headers=headers)
            if response.status_code >= 400:
                logger.warning(
                    "quota consume returned %s for %s", response.status_code, user.user_id
                )
        except httpx.HTTPError as exc:
            logger.warning("quota consume failed for %s: %s", user.user_id, exc)


def _dedupe(tools: Sequence[ToolProtocol]) -> list[ToolProtocol]:
    seen: dict[str, ToolProtocol] = {}
    for t in tools:
        seen.setdefault(t.name, t)
    return list(seen.values())


__all__ = [
    "AgentNotAvailableError",
    "ModelUnavailableError",
    "normalize_model_spec",
    "ChatService",
    "ChatTurn",
    "PreparedRun",
    "agent_instance_id",
    "frame_for",
]
