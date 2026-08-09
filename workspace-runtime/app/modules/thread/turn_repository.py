from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.thread.persistence_models import (
    ThreadModel,
    ThreadTurnExecutionModel,
    ThreadTurnModel,
)


class ThreadTurnRepository:
    """Persistence operations for logical turns and runner executions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_turn(
        self, *, thread: ThreadModel, turn_id: str, status: str
    ) -> ThreadTurnModel:
        sequence = int(
            await self.db.scalar(
                select(func.coalesce(func.max(ThreadTurnModel.sequence), 0) + 1).where(
                    ThreadTurnModel.thread_id == thread.id
                )
            )
            or 1
        )
        turn = ThreadTurnModel(
            id=turn_id,
            thread_id=thread.id,
            sequence=sequence,
            version=1,
            status=status,
        )
        self.db.add(turn)
        await self.db.flush()
        thread.active_turn_id = turn.id
        thread.version += 1
        await self.db.flush()
        return turn

    async def create_execution(
        self,
        *,
        thread: ThreadModel,
        turn: ThreadTurnModel,
        execution_id: str,
        agentic_tool: str,
        status: str,
    ) -> ThreadTurnExecutionModel:
        sequence = int(
            await self.db.scalar(
                select(
                    func.coalesce(func.max(ThreadTurnExecutionModel.sequence), 0) + 1
                ).where(ThreadTurnExecutionModel.turn_id == turn.id)
            )
            or 1
        )
        execution = ThreadTurnExecutionModel(
            id=execution_id,
            turn_id=turn.id,
            sequence=sequence,
            agentic_tool=agentic_tool,
            version=1,
            status=status,
        )
        self.db.add(execution)
        await self.db.flush()
        turn.status = "running"
        turn.completed_at = None
        turn.error_code = None
        turn.error_info = None
        thread.active_turn_id = turn.id
        thread.active_turn_execution_id = execution.id
        thread.version += 1
        turn.version += 1
        await self.db.flush()
        return execution

    async def get_turn(self, thread_id: str, turn_id: str) -> ThreadTurnModel | None:
        result = await self.db.execute(
            select(ThreadTurnModel).where(
                and_(
                    ThreadTurnModel.thread_id == thread_id,
                    ThreadTurnModel.id == turn_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_execution(self, execution_id: str) -> ThreadTurnExecutionModel | None:
        result = await self.db.execute(
            select(ThreadTurnExecutionModel)
            .where(ThreadTurnExecutionModel.id == execution_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_executions(self, turn_id: str) -> list[ThreadTurnExecutionModel]:
        result = await self.db.execute(
            select(ThreadTurnExecutionModel)
            .where(ThreadTurnExecutionModel.turn_id == turn_id)
            .order_by(ThreadTurnExecutionModel.sequence.asc())
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def list_turns_by_ids(
        self, thread_id: str, turn_ids: set[str]
    ) -> list[ThreadTurnModel]:
        if not turn_ids:
            return []
        result = await self.db.execute(
            select(ThreadTurnModel)
            .where(
                and_(
                    ThreadTurnModel.thread_id == thread_id,
                    ThreadTurnModel.id.in_(turn_ids),
                )
            )
            .order_by(ThreadTurnModel.sequence.asc())
        )
        return list(result.scalars().all())

    async def list_executions_by_ids(
        self, execution_ids: set[str]
    ) -> list[ThreadTurnExecutionModel]:
        if not execution_ids:
            return []
        result = await self.db.execute(
            select(ThreadTurnExecutionModel)
            .where(ThreadTurnExecutionModel.id.in_(execution_ids))
            .order_by(ThreadTurnExecutionModel.created_at.asc())
        )
        return list(result.scalars().all())

    async def latest_turn(self, thread_id: str) -> ThreadTurnModel | None:
        result = await self.db.execute(
            select(ThreadTurnModel)
            .where(ThreadTurnModel.thread_id == thread_id)
            .order_by(ThreadTurnModel.sequence.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def finish(
        self,
        *,
        thread: ThreadModel,
        execution: ThreadTurnExecutionModel,
        turn: ThreadTurnModel,
        status: str,
        error_code: str | None = None,
        error_info: dict | None = None,
    ) -> None:
        completed_at = datetime.now(timezone.utc)
        execution.status = status
        execution.version += 1
        execution.error_code = error_code
        execution.error_info = error_info
        execution.completed_at = completed_at
        turn.status = status
        turn.error_code = error_code
        turn.error_info = error_info
        turn.completed_at = completed_at
        turn.version += 1
        thread.version += 1
        thread.active_turn_id = None
        thread.active_turn_execution_id = None
        await self.db.flush()
