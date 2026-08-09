from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from claude_agent_sdk import CLIConnectionError, ClaudeSDKClient

from app.modules.thread.claude_sdk_options import (
    build_claude_options,
    prompt_with_attachments,
)
from app.modules.thread.execution import AgentExecutionRequest

logger = logging.getLogger(__name__)

ClientFactory = Callable[[Any], Any]


@dataclass(slots=True)
class ClaudeThreadState:
    client: Any
    active_execution_id: str | None = None
    last_used_at: float = 0.0


@dataclass(slots=True)
class ClaudeTurnStart:
    client: Any
    stream: Any


class ClaudeSdkClientManager:
    """Manage Claude SDK clients keyed by Aileron thread id."""

    def __init__(
        self,
        *,
        workspace_id: str,
        client_factory: ClientFactory | None = None,
        idle_ttl_seconds: int = 900,
    ) -> None:
        self.workspace_id = workspace_id
        self._client_factory = client_factory
        self._idle_ttl_seconds = idle_ttl_seconds
        self._states: dict[str, ClaudeThreadState] = {}
        self._execution_to_thread: dict[str, str] = {}
        self._reserved: set[str] = set()

    def reserve(self) -> str:
        execution_id = str(uuid4())
        self._reserved.add(execution_id)
        return execution_id

    def adopt_reservation(self, execution_id: str) -> None:
        self._reserved.add(execution_id)

    async def start_turn(
        self,
        *,
        thread_id: str,
        execution_id: str,
        request: AgentExecutionRequest,
        cwd: str | Path,
        now: float | None = None,
    ) -> ClaudeTurnStart:
        if execution_id not in self._reserved:
            raise ValueError("execution_not_reserved")

        state = self._states.get(thread_id)
        if state is not None and state.active_execution_id is not None:
            raise ValueError("thread_execution_active")

        if state is None:
            options = build_claude_options(
                workspace_id=self.workspace_id,
                request=request,
                cwd=cwd,
            )
            client = self._create_client(options)
            await client.connect()
            state = ClaudeThreadState(client=client)
            self._states[thread_id] = state

        await state.client.query(prompt_with_attachments(request))
        state.active_execution_id = execution_id
        state.last_used_at = time.monotonic() if now is None else now
        self._execution_to_thread[execution_id] = thread_id
        self._reserved.discard(execution_id)
        return ClaudeTurnStart(
            client=state.client, stream=state.client.receive_response()
        )

    async def stop_execution(self, execution_id: str) -> None:
        self._reserved.discard(execution_id)
        thread_id = self._execution_to_thread.get(execution_id)
        state = self._states.get(thread_id) if thread_id is not None else None
        if state is not None and state.active_execution_id == execution_id:
            try:
                await state.client.interrupt()
            except CLIConnectionError:
                pass
            except Exception:
                logger.debug(
                    "Claude SDK interrupt failed: execution_id=%s",
                    execution_id,
                    exc_info=True,
                )
        if thread_id is not None:
            await self._disconnect_thread(thread_id)

    def is_alive(self, execution_id: str) -> bool:
        if execution_id in self._reserved:
            return True
        state = self._state_for_execution(execution_id)
        return bool(state and state.active_execution_id == execution_id)

    async def finish_execution(
        self,
        execution_id: str,
        *,
        now: float | None = None,
    ) -> None:
        self._reserved.discard(execution_id)
        thread_id = self._execution_to_thread.pop(execution_id, None)
        if thread_id is None:
            return
        state = self._states.get(thread_id)
        if state is not None and state.active_execution_id == execution_id:
            state.active_execution_id = None
            state.last_used_at = time.monotonic() if now is None else now

    async def destroy_thread(self, thread_id: str) -> None:
        await self._disconnect_thread(thread_id)

    async def evict_idle(self, *, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        evicted = 0
        for thread_id, state in list(self._states.items()):
            if state.active_execution_id is not None:
                continue
            if current - state.last_used_at < self._idle_ttl_seconds:
                continue
            await self._disconnect_thread(thread_id)
            evicted += 1
        return evicted

    def _create_client(self, options: Any) -> Any:
        if self._client_factory is not None:
            return self._client_factory(options)
        return ClaudeSDKClient(options=options)

    async def _disconnect_thread(self, thread_id: str) -> None:
        state = self._states.pop(thread_id, None)
        if state is None:
            return
        for execution_id, mapped_thread_id in list(self._execution_to_thread.items()):
            if mapped_thread_id == thread_id:
                self._execution_to_thread.pop(execution_id, None)
                self._reserved.discard(execution_id)
        try:
            await state.client.disconnect()
        except Exception:
            logger.debug(
                "Claude SDK disconnect failed: thread_id=%s",
                thread_id,
                exc_info=True,
            )

    def _state_for_execution(self, execution_id: str) -> ClaudeThreadState | None:
        thread_id = self._execution_to_thread.get(execution_id)
        return self._states.get(thread_id) if thread_id else None
