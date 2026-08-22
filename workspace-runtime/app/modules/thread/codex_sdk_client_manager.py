from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from openai_codex import (
    ApprovalMode,
    AsyncCodex,
    ImageInput,
    LocalImageInput,
    Sandbox,
    TextInput,
)
from openai_codex.client import CodexConfig

from app.modules.cli_settings.user_scope.paths import get_codex_path_resolver
from app.modules.thread.mcp.agent_policy import AILERON_MCP_POLICY_PROMPT
from app.modules.thread.mcp.config import (
    codex_aileron_mcp_config_overrides,
    codex_aileron_mcp_thread_config,
)

logger = logging.getLogger(__name__)

CODEX_AILERON_MCP_PROMPT = AILERON_MCP_POLICY_PROMPT


@dataclass(slots=True)
class CodexThreadState:
    codex: Any
    thread: Any | None = None
    codex_thread_id: str | None = None
    active_turn: Any | None = None
    active_execution_id: str | None = None
    last_used_at: float = 0.0


@dataclass(slots=True)
class CodexTurnStart:
    codex: Any
    thread: Any
    turn: Any
    codex_thread_id: str


class CodexSdkClientManager:
    """Manage Codex SDK app-server state keyed by Aileron thread id."""

    def __init__(
        self,
        *,
        codex_factory: Callable[[], Any] | None = None,
        codex_bin: str | None = None,
        codex_home: str | None = None,
        idle_ttl_seconds: int = 900,
    ) -> None:
        self._codex_factory = codex_factory
        self._codex_bin = codex_bin
        self._codex_home = codex_home or str(get_codex_path_resolver().codex_home)
        self._idle_ttl_seconds = idle_ttl_seconds
        self._states: dict[str, CodexThreadState] = {}
        self._execution_to_thread: dict[str, str] = {}
        self._reserved: set[str] = set()
        self._startup_finalizers: set[asyncio.Task[None]] = set()

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
        prompt: str,
        attachments: list[dict[str, Any]],
        cwd: str,
        resume_session_id: str | None,
        model: str | None,
        now: float | None = None,
    ) -> CodexTurnStart:
        if execution_id not in self._reserved:
            raise ValueError("execution_not_reserved")
        state: CodexThreadState | None = None
        claimed = False
        cancelled_startup_task: asyncio.Task[Any] | None = None
        try:
            state = self._states.get(thread_id)
            if state is not None and state.active_execution_id is not None:
                raise ValueError("thread_execution_active")
            if state is None:
                state = CodexThreadState(codex=self._create_codex(cwd))
                self._states[thread_id] = state

            # Claim the state before the first SDK await. This makes startup visible
            # as active to both idle eviction and competing starts.
            state.active_execution_id = execution_id
            claimed = True
            self._execution_to_thread[execution_id] = thread_id
            self._reserved.discard(execution_id)

            if state.thread is None:
                if resume_session_id:
                    startup = state.codex.thread_resume(
                        resume_session_id,
                        cwd=cwd,
                        sandbox=Sandbox.full_access,
                        approval_mode=ApprovalMode.deny_all,
                        model=model,
                        config=codex_aileron_mcp_thread_config(),
                        developer_instructions=CODEX_AILERON_MCP_PROMPT,
                    )
                else:
                    startup = state.codex.thread_start(
                        cwd=cwd,
                        sandbox=Sandbox.full_access,
                        approval_mode=ApprovalMode.deny_all,
                        model=model,
                        config=codex_aileron_mcp_thread_config(),
                        developer_instructions=CODEX_AILERON_MCP_PROMPT,
                    )
                # The bundled SDK starts its process in a worker thread. Shield its
                # completion signal so cancellation cannot orphan a late process.
                startup_task = asyncio.create_task(
                    startup,
                    name=f"codex-sdk-startup:{execution_id}",
                )
                try:
                    thread = await asyncio.shield(startup_task)
                except asyncio.CancelledError:
                    cancelled_startup_task = startup_task
                    raise
                self._ensure_start_active(thread_id, execution_id, state)
                state.thread = thread
                state.codex_thread_id = thread.id

            turn = await state.thread.turn(
                self._run_input(prompt, attachments),
                cwd=cwd,
                sandbox=Sandbox.full_access,
                approval_mode=ApprovalMode.deny_all,
                model=model,
            )
            self._ensure_start_active(thread_id, execution_id, state)
            state.active_turn = turn
            state.last_used_at = time.monotonic() if now is None else now
            return CodexTurnStart(
                codex=state.codex,
                thread=state.thread,
                turn=turn,
                codex_thread_id=str(state.codex_thread_id),
            )
        except BaseException:
            try:
                if claimed and state is not None:
                    await self._rollback_start(thread_id, execution_id, state)
                else:
                    self._reserved.discard(execution_id)
            finally:
                if cancelled_startup_task is not None and state is not None:
                    self._schedule_startup_finalizer(
                        thread_id,
                        execution_id,
                        state,
                        cancelled_startup_task,
                    )
            raise

    async def stop_execution(self, execution_id: str) -> None:
        self._reserved.discard(execution_id)
        thread_id = self._execution_to_thread.get(execution_id)
        if thread_id is None:
            return
        state = self._states.get(thread_id)
        if state is None or state.active_execution_id != execution_id:
            return
        if state.active_turn is None:
            await self._close_thread_state(thread_id, expected_state=state)
            return
        await state.active_turn.interrupt()

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
        if state and state.active_execution_id == execution_id:
            state.active_execution_id = None
            state.active_turn = None
            state.last_used_at = time.monotonic() if now is None else now

    async def destroy_thread(self, thread_id: str) -> None:
        await self._close_thread_state(thread_id)

    async def evict_idle(self, *, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        evicted = 0
        for thread_id, state in list(self._states.items()):
            if state.active_execution_id is not None:
                continue
            if current - state.last_used_at < self._idle_ttl_seconds:
                continue
            if await self._close_thread_state(thread_id, expected_state=state):
                evicted += 1
        return evicted

    async def _close_thread_state(
        self,
        thread_id: str,
        *,
        expected_state: CodexThreadState | None = None,
    ) -> bool:
        state = self._states.get(thread_id)
        if state is None or (
            expected_state is not None and state is not expected_state
        ):
            return False
        self._states.pop(thread_id)
        for execution_id, mapped_thread_id in list(self._execution_to_thread.items()):
            if mapped_thread_id == thread_id:
                self._execution_to_thread.pop(execution_id, None)
                self._reserved.discard(execution_id)
        await state.codex.close()
        return True

    def _create_codex(self, cwd: str) -> Any:
        if self._codex_factory is not None:
            return self._codex_factory()
        return AsyncCodex(
            config=CodexConfig(
                codex_bin=self._codex_bin,
                config_overrides=codex_aileron_mcp_config_overrides(),
                cwd=cwd,
                env={
                    "CODEX_HOME": self._codex_home,
                    "AILERON_CODEX_SESSION_STATE_DIR": str(
                        Path(self._codex_home) / ".aileron-sdk-sessions"
                    ),
                },
            )
        )

    def _run_input(self, prompt: str, attachments: list[dict[str, Any]]) -> list[Any]:
        items: list[Any] = [TextInput(prompt)]
        for attachment in attachments:
            path = str(attachment.get("path") or "")
            if not path:
                continue
            mime_type = str(attachment.get("mimeType") or "")
            name = str(attachment.get("name") or Path(path).name)
            if mime_type.startswith("image/"):
                if path.startswith(("http://", "https://")):
                    items.append(ImageInput(path))
                else:
                    items.append(LocalImageInput(path))
                continue
            items.append(TextInput(f"Attached file: {name} ({path})"))
        return items

    def _state_for_execution(self, execution_id: str) -> CodexThreadState | None:
        thread_id = self._execution_to_thread.get(execution_id)
        return self._states.get(thread_id) if thread_id else None

    def _ensure_start_active(
        self,
        thread_id: str,
        execution_id: str,
        state: CodexThreadState,
    ) -> None:
        if (
            self._states.get(thread_id) is not state
            or state.active_execution_id != execution_id
            or self._execution_to_thread.get(execution_id) != thread_id
        ):
            raise RuntimeError("execution_stopped_during_startup")

    async def _cleanup_startup_state(
        self,
        thread_id: str,
        execution_id: str,
        state: CodexThreadState,
    ) -> None:
        try:
            await state.codex.close()
        except BaseException:
            logger.debug(
                "Codex SDK startup cleanup failed: thread_id=%s execution_id=%s",
                thread_id,
                execution_id,
                exc_info=True,
            )

    def _schedule_startup_finalizer(
        self,
        thread_id: str,
        execution_id: str,
        state: CodexThreadState,
        startup_task: asyncio.Task[Any],
    ) -> None:
        finalizer = asyncio.create_task(
            self._finalize_cancelled_startup(
                thread_id,
                execution_id,
                state,
                startup_task,
            ),
            name=f"codex-sdk-startup-finalizer:{execution_id}",
        )
        # asyncio keeps only weak task references; retain cleanup until it finishes.
        self._startup_finalizers.add(finalizer)
        finalizer.add_done_callback(self._discard_startup_finalizer)

    async def _finalize_cancelled_startup(
        self,
        thread_id: str,
        execution_id: str,
        state: CodexThreadState,
        startup_task: asyncio.Task[Any],
    ) -> None:
        while not startup_task.done():
            try:
                await asyncio.shield(startup_task)
            except asyncio.CancelledError:
                if startup_task.done():
                    break
                continue
            except BaseException:
                break
        try:
            startup_task.result()
        except asyncio.CancelledError:
            logger.debug(
                "Codex SDK cancelled startup task did not materialize: "
                "thread_id=%s execution_id=%s",
                thread_id,
                execution_id,
            )
        except BaseException:
            logger.debug(
                "Codex SDK cancelled startup task finished with an error: "
                "thread_id=%s execution_id=%s",
                thread_id,
                execution_id,
                exc_info=True,
            )
        await self._cleanup_startup_state(thread_id, execution_id, state)

    def _discard_startup_finalizer(
        self,
        completed: asyncio.Task[None],
    ) -> None:
        self._startup_finalizers.discard(completed)
        try:
            completed.result()
        except asyncio.CancelledError:
            logger.debug("Codex SDK startup finalizer was cancelled")
        except BaseException:
            logger.exception("Codex SDK startup finalizer failed")

    async def _rollback_start(
        self,
        thread_id: str,
        execution_id: str,
        state: CodexThreadState,
    ) -> None:
        self._reserved.discard(execution_id)
        current_state = self._states.get(thread_id)
        if current_state is not state:
            if state.active_execution_id == execution_id:
                state.active_execution_id = None
                state.active_turn = None
            if self._execution_to_thread.get(execution_id) == thread_id:
                self._execution_to_thread.pop(execution_id, None)
            await self._cleanup_startup_state(thread_id, execution_id, state)
            return
        if state.active_execution_id != execution_id:
            return

        state.active_execution_id = None
        state.active_turn = None
        self._states.pop(thread_id, None)
        if self._execution_to_thread.get(execution_id) == thread_id:
            self._execution_to_thread.pop(execution_id, None)
        await self._cleanup_startup_state(thread_id, execution_id, state)
