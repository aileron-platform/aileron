from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.modules.thread.codex_sdk_client_manager import CodexSdkClientManager
from app.modules.thread.codex_sdk_event_mapper import CodexSdkEventMapper
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)
from app.modules.version_control.repository import GitUtils
from app.modules.version_control.worktree_config import get_worktree_subdir

logger = logging.getLogger(__name__)

EventCallback = Callable[[AgentEvent], Awaitable[None] | None]
CwdResolver = Callable[[str | None], Path | str]


class CodexSdkAgentRunner:
    """Run Codex turns through the Python SDK app-server."""

    def __init__(
        self,
        *,
        workspace_id: str,
        manager: CodexSdkClientManager | None = None,
        cwd_resolver: CwdResolver | None = None,
    ) -> None:
        self.workspace_id = workspace_id
        self._manager = manager or CodexSdkClientManager()
        self._cwd_resolver = cwd_resolver or self._resolve_cwd
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def reserve(self) -> str:
        return self._manager.reserve()

    def adopt_reservation(self, execution_id: str) -> None:
        self._manager.adopt_reservation(execution_id)

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: EventCallback,
        execution_id: str,
    ) -> None:
        cwd = str(self._cwd_resolver(request.git_context_id))
        task = asyncio.create_task(
            self._run_turn(
                thread_id=request.thread_id,
                execution_id=execution_id,
                request=request,
                cwd=cwd,
                on_event=on_event,
            ),
            name=f"codex-sdk-runner:{execution_id}",
        )
        self._tasks[execution_id] = task

        def discard_completed(completed: asyncio.Task[None]) -> None:
            self._discard_task(execution_id, completed)

        task.add_done_callback(discard_completed)

    async def stop(self, execution_id: str) -> None:
        await self._manager.stop_execution(execution_id)
        task = self._tasks.get(execution_id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.pop(execution_id, None)

    def is_alive(self, execution_id: str) -> bool:
        task = self._tasks.get(execution_id)
        if task is not None and not task.done():
            return True
        return self._manager.is_alive(execution_id)

    async def wait(self, execution_id: str) -> None:
        task = self._tasks.get(execution_id)
        if task is None:
            return
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if not task.cancelled():
                raise
        finally:
            if task.done():
                self._tasks.pop(execution_id, None)

    async def destroy_thread(self, thread_id: str) -> None:
        await self._manager.destroy_thread(thread_id)

    async def evict_idle(self) -> int:
        return await self._manager.evict_idle()

    async def _run_turn(
        self,
        *,
        thread_id: str,
        execution_id: str,
        request: AgentExecutionRequest,
        cwd: str,
        on_event: EventCallback,
    ) -> None:
        mapper = CodexSdkEventMapper()
        try:
            started = await self._manager.start_turn(
                thread_id=thread_id,
                execution_id=execution_id,
                prompt=request.prompt_text,
                attachments=request.attachments,
                cwd=cwd,
                resume_session_id=request.agent_resume_id,
                model=request.model,
            )
            await self._emit(
                on_event,
                AgentEvent(
                    type="system_init",
                    content={
                        "agentResumeId": started.codex_thread_id,
                        "model": request.model,
                        "cwd": cwd,
                        "tools": [],
                        "mcpServers": [],
                    },
                ),
            )
            async for notification in started.turn.stream():
                if notification.method == "turn/completed":
                    complete = mapper.complete_event()
                    if complete is not None:
                        await self._emit(on_event, complete)
                    return
                for event in mapper.map_notification(
                    notification.method,
                    notification.payload,
                ):
                    await self._emit(on_event, event)
                    if event.type == "error":
                        await self._manager.destroy_thread(thread_id)
                        return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Codex SDK turn failed: execution_id=%s", execution_id)
            await self._emit(
                on_event,
                AgentEvent(
                    type="error",
                    content={"parts": [{"type": "text", "text": str(exc)}]},
                    error_code="codex_execution_failed",
                    error_info={
                        "exception": type(exc).__name__,
                        "message": str(exc),
                    },
                ),
            )
            await self._manager.destroy_thread(thread_id)
        finally:
            await self._manager.finish_execution(execution_id)

    async def _emit(self, on_event: EventCallback, event: AgentEvent) -> None:
        result = on_event(event)
        if inspect.isawaitable(result):
            await result

    def _discard_task(self, execution_id: str, completed: asyncio.Task[None]) -> None:
        if self._tasks.get(execution_id) is completed:
            self._tasks.pop(execution_id, None)

    def _resolve_cwd(self, git_context_id: str | None) -> Path:
        workspace_root = Path("/workspace").resolve()
        utils = GitUtils(workspace_root, worktree_subdir=get_worktree_subdir())
        return utils.resolve_context_path(self.workspace_id, git_context_id)
