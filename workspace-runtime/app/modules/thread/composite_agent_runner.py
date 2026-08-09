from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
    AgentRunner,
)
from app.modules.runtime_control.state import get_runtime_admission_state

EventCallback = Callable[[AgentEvent], Awaitable[None] | None]
logger = logging.getLogger(__name__)


class CompositeAgentRunner:
    """Route agent executions after request context is available."""

    def __init__(
        self,
        *,
        opencode_runner: AgentRunner,
        codex_runner: AgentRunner,
        claude_runner: AgentRunner,
    ) -> None:
        self._opencode_runner = opencode_runner
        self._codex_runner = codex_runner
        self._claude_runner = claude_runner
        self._reserved: set[str] = set()
        self._owners: dict[str, AgentRunner] = {}
        self._execution_threads: dict[str, str] = {}
        self._cleanup_watchers: dict[str, asyncio.Task[None]] = {}

    def reserve(self) -> str:
        get_runtime_admission_state().require_accepting()
        execution_id = str(uuid4())
        self._reserved.add(execution_id)
        return execution_id

    def adopt_reservation(self, execution_id: str) -> None:
        get_runtime_admission_state().require_accepting()
        self._reserved.add(execution_id)

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: EventCallback,
        execution_id: str,
    ) -> None:
        get_runtime_admission_state().require_accepting()
        if execution_id not in self._reserved:
            raise ValueError("execution_not_reserved")
        try:
            runner = self._runner_for_tool(request.agentic_tool)
        except Exception:
            self._reserved.discard(execution_id)
            raise
        self._owners[execution_id] = runner
        self._execution_threads[execution_id] = request.thread_id
        self._reserved.discard(execution_id)
        try:
            runner.adopt_reservation(execution_id)
            await runner.start(
                request,
                lambda event: self._handle_event(execution_id, on_event, event),
                execution_id,
            )
            self._cleanup_watchers[execution_id] = asyncio.create_task(
                self._watch_execution(execution_id, runner),
                name=f"composite-agent-cleanup:{execution_id}",
            )
        except Exception:
            with contextlib.suppress(Exception):
                await runner.stop(execution_id)
            self._owners.pop(execution_id, None)
            self._execution_threads.pop(execution_id, None)
            self._reserved.discard(execution_id)
            raise

    async def wait(self, execution_id: str) -> None:
        runner = self._owners.get(execution_id)
        if runner is not None:
            await runner.wait(execution_id)

    async def stop(self, execution_id: str) -> None:
        self._reserved.discard(execution_id)
        runner = self._owners.get(execution_id)
        if runner is not None:
            await runner.stop(execution_id)

    def is_alive(self, execution_id: str) -> bool:
        if execution_id in self._reserved:
            return True
        runner = self._owners.get(execution_id)
        if runner is not None:
            return runner.is_alive(execution_id)
        return False

    async def destroy_thread(self, thread_id: str) -> None:
        for execution_id, mapped_thread_id in list(self._execution_threads.items()):
            if mapped_thread_id != thread_id:
                continue
            await self.stop(execution_id)
        await self._opencode_runner.destroy_thread(thread_id)
        await self._codex_runner.destroy_thread(thread_id)
        await self._claude_runner.destroy_thread(thread_id)

    async def drain_all(self) -> None:
        """Stop every reserved or active agent execution for all actors."""

        self._reserved.clear()
        execution_ids = list(self._owners)
        stop_results = await asyncio.gather(
            *(self.stop(execution_id) for execution_id in execution_ids),
            return_exceptions=True,
        )
        wait_results = await asyncio.gather(
            *(self.wait(execution_id) for execution_id in execution_ids),
            return_exceptions=True,
        )
        failures = [
            result
            for result in [*stop_results, *wait_results]
            if isinstance(result, BaseException)
        ]
        if failures or any(
            self.is_alive(execution_id) for execution_id in execution_ids
        ):
            raise RuntimeError("agent_drain_incomplete")

    async def evict_idle(self) -> int:
        return (
            await self._opencode_runner.evict_idle()
            + await self._codex_runner.evict_idle()
            + await self._claude_runner.evict_idle()
        )

    async def _handle_event(
        self,
        execution_id: str,
        on_event: EventCallback,
        event: AgentEvent,
    ) -> None:
        result = on_event(event)
        if inspect.isawaitable(result):
            await result

    async def _watch_execution(
        self,
        execution_id: str,
        runner: AgentRunner,
    ) -> None:
        try:
            await runner.wait(execution_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Agent runner cleanup wait failed: execution_id=%s",
                execution_id,
            )
        finally:
            if self._owners.get(execution_id) is runner:
                self._owners.pop(execution_id, None)
                self._execution_threads.pop(execution_id, None)
            self._reserved.discard(execution_id)
            current = asyncio.current_task()
            if self._cleanup_watchers.get(execution_id) is current:
                self._cleanup_watchers.pop(execution_id, None)

    def _runner_for_tool(self, agentic_tool: str) -> AgentRunner:
        if agentic_tool == "opencode":
            return self._opencode_runner
        if agentic_tool == "codex":
            return self._codex_runner
        if agentic_tool == "claude":
            return self._claude_runner
        raise ValueError(f"unsupported_agentic_tool:{agentic_tool}")
