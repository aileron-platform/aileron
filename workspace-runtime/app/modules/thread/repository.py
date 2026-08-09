from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from sqlalchemy import and_, case, delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.modules.thread.domain.enums import (
    RUNTIME_RESTART_RECONCILIATION_STATUSES,
    RUNNING_STATUSES,
    ThreadStatus,
)
from app.modules.thread.persistence_models import (
    ThreadMessageModel,
    ThreadModel,
    ThreadToolResultContentModel,
    ThreadTurnExecutionModel,
    ThreadTurnModel,
)


class ThreadDeleteResult(str, Enum):
    DELETED = "deleted"
    NOT_FOUND = "not_found"
    RUNNING = "running"


class ThreadRepository:
    """Workspace-scoped thread repository."""

    def __init__(self, db: AsyncSession, workspace_id: str) -> None:
        self.db = db
        self.workspace_id = workspace_id

    async def create(self, thread: ThreadModel) -> ThreadModel:
        self.db.add(thread)
        await self.db.flush()
        await self.db.refresh(thread)
        return thread

    async def create_or_get_automation(self, thread: ThreadModel) -> ThreadModel:
        automation_execution_id = thread.automation_execution_id
        if thread.origin != "automation" or automation_execution_id is None:
            raise ValueError("automation_thread_identity_required")

        existing = await self.get_by_automation_execution(automation_execution_id)
        if existing is not None:
            return existing

        try:
            async with self.db.begin_nested():
                self.db.add(thread)
                await self.db.flush()
        except IntegrityError:
            existing = await self.get_by_automation_execution(automation_execution_id)
            if existing is None:
                raise
            return existing

        await self.db.refresh(thread)
        return thread

    async def get_by_automation_execution(
        self, automation_execution_id: str
    ) -> ThreadModel | None:
        stmt = select(ThreadModel).where(
            and_(
                ThreadModel.workspace_id == self.workspace_id,
                ThreadModel.origin == "automation",
                ThreadModel.automation_execution_id == automation_execution_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get(self, thread_id: str, user_id: str) -> ThreadModel | None:
        stmt = select(ThreadModel).where(
            and_(
                ThreadModel.id == thread_id,
                ThreadModel.workspace_id == self.workspace_id,
                ThreadModel.origin == "user",
                ThreadModel.user_id == user_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_readable(self, thread_id: str, user_id: str) -> ThreadModel | None:
        """Resolve a thread after the caller's workspace membership was verified."""
        stmt = select(ThreadModel).where(
            and_(
                ThreadModel.id == thread_id,
                ThreadModel.workspace_id == self.workspace_id,
                (
                    (ThreadModel.origin == "automation")
                    | (
                        (ThreadModel.origin == "user")
                        & (ThreadModel.user_id == user_id)
                    )
                ),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str, archived: bool) -> list[ThreadModel]:
        stmt = (
            select(ThreadModel)
            .options(
                load_only(
                    ThreadModel.id,
                    ThreadModel.workspace_id,
                    ThreadModel.user_id,
                    ThreadModel.origin,
                    ThreadModel.automation_job_id,
                    ThreadModel.automation_execution_id,
                    ThreadModel.title,
                    ThreadModel.agentic_tool,
                    ThreadModel.model,
                    ThreadModel.claude_mode,
                    ThreadModel.status,
                    ThreadModel.version,
                    ThreadModel.active_turn_id,
                    ThreadModel.active_turn_execution_id,
                    ThreadModel.git_context_id,
                    ThreadModel.context_tokens,
                    ThreadModel.context_window,
                    ThreadModel.archived,
                    ThreadModel.error_code,
                    ThreadModel.error_info,
                    ThreadModel.error_message,
                    ThreadModel.created_at,
                    ThreadModel.updated_at,
                )
            )
            .where(
                and_(
                    ThreadModel.workspace_id == self.workspace_id,
                    ThreadModel.user_id == user_id,
                    ThreadModel.origin == "user",
                    ThreadModel.archived == archived,
                )
            )
            .order_by(
                case(
                    (
                        ThreadModel.status == ThreadStatus.DRAFT.value,
                        ThreadModel.created_at,
                    ),
                    else_=ThreadModel.updated_at,
                ).desc(),
                ThreadModel.created_at.desc(),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, thread_id: str, user_id: str) -> ThreadDeleteResult:
        stmt = (
            select(ThreadModel)
            .where(
                and_(
                    ThreadModel.id == thread_id,
                    ThreadModel.workspace_id == self.workspace_id,
                    ThreadModel.user_id == user_id,
                    ThreadModel.origin == "user",
                )
            )
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        thread = result.scalar_one_or_none()
        if thread is None:
            return ThreadDeleteResult.NOT_FOUND
        if ThreadStatus(thread.status) in RUNNING_STATUSES:
            return ThreadDeleteResult.RUNNING

        message_ids = select(ThreadMessageModel.id).where(
            ThreadMessageModel.thread_id == thread_id
        )
        turn_ids = select(ThreadTurnModel.id).where(
            ThreadTurnModel.thread_id == thread_id
        )
        await self.db.execute(
            delete(ThreadToolResultContentModel).where(
                ThreadToolResultContentModel.message_id.in_(message_ids)
            )
        )
        await self.db.execute(
            delete(ThreadMessageModel).where(ThreadMessageModel.thread_id == thread_id)
        )
        await self.db.execute(
            delete(ThreadTurnExecutionModel).where(
                ThreadTurnExecutionModel.turn_id.in_(turn_ids)
            )
        )
        await self.db.execute(
            delete(ThreadTurnModel).where(ThreadTurnModel.thread_id == thread_id)
        )
        await self.db.execute(
            delete(ThreadModel).where(
                and_(
                    ThreadModel.id == thread_id,
                    ThreadModel.workspace_id == self.workspace_id,
                    ThreadModel.user_id == user_id,
                    ThreadModel.origin == "user",
                )
            )
        )
        await self.db.flush()
        return ThreadDeleteResult.DELETED

    async def locked_update(
        self,
        thread_id: str,
        mutate: Callable[[ThreadModel], None],
    ) -> ThreadModel | None:
        stmt = (
            select(ThreadModel)
            .where(
                and_(
                    ThreadModel.id == thread_id,
                    ThreadModel.workspace_id == self.workspace_id,
                )
            )
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        thread = result.scalar_one_or_none()
        if thread is None:
            return None

        mutate(thread)
        if inspect(thread).modified:
            thread.version += 1
        await self.db.flush()
        await self.db.refresh(thread)
        return thread

    async def list_reconcilable_running(self) -> list[ThreadModel]:
        stmt = select(ThreadModel).where(
            and_(
                ThreadModel.workspace_id == self.workspace_id,
                ThreadModel.status.in_(
                    [status.value for status in RUNTIME_RESTART_RECONCILIATION_STATUSES]
                ),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
