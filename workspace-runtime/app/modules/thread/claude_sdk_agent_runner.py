from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.modules.thread.claude_sdk_client_manager import (
    ClaudeSdkClientManager,
)
from app.modules.thread.claude_sdk_event_mapper import ClaudeSdkEventMapper
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)
from app.modules.version_control.repository import GitUtils
from app.modules.version_control.worktree_config import get_worktree_subdir

logger = logging.getLogger(__name__)

EventCallback = Callable[[AgentEvent], Awaitable[None] | None]
CwdResolver = Callable[[str | None], Path | str]


class ClaudeSdkAgentRunner:
    """Run Claude turns through the Python SDK client."""

    def __init__(
        self,
        *,
        workspace_id: str,
        manager: ClaudeSdkClientManager | None = None,
        cwd_resolver: CwdResolver | None = None,
    ) -> None:
        self.workspace_id = workspace_id
        self._manager = manager or ClaudeSdkClientManager(workspace_id=workspace_id)
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
            name=f"claude-sdk-runner:{execution_id}",
        )
        self._tasks[execution_id] = task

        def discard_completed(completed: asyncio.Task[None]) -> None:
            self._discard_task(execution_id, completed)

        task.add_done_callback(discard_completed)

    async def stop(self, execution_id: str) -> None:
        task = self._tasks.get(execution_id)
        stop_error: BaseException | None = None
        task_error: BaseException | None = None
        try:
            await self._manager.stop_execution(execution_id)
        except BaseException as exc:
            stop_error = exc

        if task is not None:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except BaseException as exc:
                task_error = exc
        if self._tasks.get(execution_id) is task:
            self._tasks.pop(execution_id, None)

        if stop_error is not None:
            if task_error is not None:
                logger.debug(
                    "Claude SDK runner task cleanup failed after manager stop error: "
                    "execution_id=%s",
                    execution_id,
                    exc_info=(
                        type(task_error),
                        task_error,
                        task_error.__traceback__,
                    ),
                )
            raise stop_error
        if task_error is not None:
            raise task_error

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
        mapper = ClaudeSdkEventMapper()
        try:
            started = await self._manager.start_turn(
                thread_id=thread_id,
                execution_id=execution_id,
                request=request,
                cwd=cwd,
            )
            async for message in started.stream:
                for event in mapper.map_message(message):
                    await self._emit(on_event, event)
                    if event.type == "error":
                        await self._manager.destroy_thread(thread_id)
                        return
            complete = mapper.complete_event()
            if complete is not None:
                await self._emit(on_event, complete)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Claude SDK turn failed: execution_id=%s", execution_id)
            await self._emit(
                on_event,
                AgentEvent(
                    type="error",
                    content={"parts": [{"type": "text", "text": str(exc)}]},
                    error_code="claude_execution_failed",
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
