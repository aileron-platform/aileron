from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.thread.domain.enums import (
    RUNTIME_RESTART_RECONCILIATION_STATUSES,
    ThreadStatus,
)
from app.modules.thread.persistence_models import ThreadModel
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.turn_repository import ThreadTurnRepository
from app.modules.thread.state_changes import apply_thread_error


class RunnerHealth(Protocol):
    def is_alive(self, execution_id: str) -> bool: ...


async def reconcile_stale_running_threads(
    db: AsyncSession,
    *,
    workspace_id: str,
    runner: RunnerHealth,
) -> int:
    """Mark running threads without a live agent process as retryable errors."""
    repo = ThreadRepository(db, workspace_id=workspace_id)
    turn_repo = ThreadTurnRepository(db)
    reconciled = 0

    for thread in await repo.list_reconcilable_running():
        active_execution_id = thread.active_turn_execution_id
        if active_execution_id is not None and runner.is_alive(active_execution_id):
            continue

        def mutate(model: ThreadModel) -> None:
            if (
                ThreadStatus(model.status)
                not in RUNTIME_RESTART_RECONCILIATION_STATUSES
            ):
                return
            if model.active_turn_execution_id != active_execution_id:
                return
            apply_thread_error(
                model,
                error_code="runtime_restarted",
                error_message=None,
                error_info={"active_execution_id": active_execution_id},
                preserve_existing_specific=False,
            )

        updated = await repo.locked_update(thread.id, mutate)
        if updated is not None and updated.status == ThreadStatus.ERROR.value:
            if active_execution_id is not None:
                execution = await turn_repo.get_execution(active_execution_id)
                turn = (
                    await turn_repo.get_turn(updated.id, execution.turn_id)
                    if execution is not None
                    else None
                )
                if execution is not None and turn is not None:
                    await turn_repo.finish(
                        thread=updated,
                        execution=execution,
                        turn=turn,
                        status="error",
                        error_code="runtime_restarted",
                        error_info={"active_execution_id": active_execution_id},
                    )
            reconciled += 1

    return reconciled
