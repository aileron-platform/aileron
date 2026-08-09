from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.thread.domain.enums import ThreadStatus
from app.modules.thread.persistence_models import ThreadModel
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.turn_repository import ThreadTurnRepository
from app.modules.thread.reconciliation import reconcile_stale_running_threads
from tests.unit.modules.thread.db_fixture import drop_thread_tables, reset_thread_tables


@pytest.fixture
async def reconciliation_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    async with postgres_engine.begin() as conn:
        await reset_thread_tables(conn)

    session_factory = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with postgres_engine.begin() as conn:
        await drop_thread_tables(conn)


@dataclass
class FakeRunner:
    alive_execution_ids: set[str]

    def is_alive(self, execution_id: str) -> bool:
        return execution_id in self.alive_execution_ids


async def create_thread(
    session: AsyncSession,
    *,
    thread_id: str,
    status: ThreadStatus,
    active_turn_execution_id: str | None,
) -> ThreadModel:
    thread = await ThreadRepository(session, workspace_id="workspace-a").create(
        ThreadModel(
            id=thread_id,
            workspace_id="workspace-a",
            user_id="user-a",
            origin="user",
            title="Running thread",
            agentic_tool="claude",
            model="claude-opus-4-8",
            claude_mode="execute",
            status=status.value,
            queued_messages=[],
            draft_message=None,
            archived=False,
        )
    )
    if active_turn_execution_id is not None:
        turn_repo = ThreadTurnRepository(session)
        turn = await turn_repo.create_turn(
            thread=thread,
            turn_id=f"{thread_id}-turn",
            status=status.value,
        )
        execution = await turn_repo.create_execution(
            thread=thread,
            turn=turn,
            execution_id=active_turn_execution_id,
            agentic_tool=thread.agentic_tool,
            status=status.value,
        )
        turn.status = status.value
        execution.status = status.value
    return thread


@pytest.mark.asyncio
async def test_reconcile_marks_running_threads_without_live_process_as_retryable_error(
    reconciliation_session: AsyncSession,
) -> None:
    stale = await create_thread(
        reconciliation_session,
        thread_id="stale-thread",
        status=ThreadStatus.WORKING,
        active_turn_execution_id="missing-execution",
    )
    alive = await create_thread(
        reconciliation_session,
        thread_id="alive-thread",
        status=ThreadStatus.WORKING,
        active_turn_execution_id="alive-execution",
    )
    complete = await create_thread(
        reconciliation_session,
        thread_id="complete-thread",
        status=ThreadStatus.COMPLETE,
        active_turn_execution_id=None,
    )
    await reconciliation_session.commit()

    reconciled = await reconcile_stale_running_threads(
        reconciliation_session,
        workspace_id="workspace-a",
        runner=FakeRunner(alive_execution_ids={"alive-execution"}),
    )

    assert reconciled == 1
    await reconciliation_session.refresh(stale)
    await reconciliation_session.refresh(alive)
    await reconciliation_session.refresh(complete)
    assert stale.status == ThreadStatus.ERROR.value
    assert stale.active_turn_execution_id is None
    assert stale.error_code == "runtime_restarted"
    assert stale.error_info == {"active_execution_id": "missing-execution"}
    assert stale.error_message is None
    assert alive.status == ThreadStatus.WORKING.value
    assert complete.status == ThreadStatus.COMPLETE.value


@pytest.mark.asyncio
async def test_reconcile_treats_running_thread_without_active_execution_as_stale(
    reconciliation_session: AsyncSession,
) -> None:
    thread = await create_thread(
        reconciliation_session,
        thread_id="booting-thread",
        status=ThreadStatus.BOOTING,
        active_turn_execution_id=None,
    )
    await reconciliation_session.commit()

    reconciled = await reconcile_stale_running_threads(
        reconciliation_session,
        workspace_id="workspace-a",
        runner=FakeRunner(alive_execution_ids=set()),
    )

    assert reconciled == 1
    await reconciliation_session.refresh(thread)
    assert thread.status == ThreadStatus.ERROR.value
    assert thread.active_turn_execution_id is None
    assert thread.error_code == "runtime_restarted"
    assert thread.error_info == {"active_execution_id": None}


@pytest.mark.asyncio
async def test_reconcile_marks_queued_thread_with_missing_agent_process_as_retryable_error(
    reconciliation_session: AsyncSession,
) -> None:
    thread = await create_thread(
        reconciliation_session,
        thread_id="queued-thread",
        status=ThreadStatus.QUEUED,
        active_turn_execution_id="missing-execution",
    )
    await reconciliation_session.commit()

    reconciled = await reconcile_stale_running_threads(
        reconciliation_session,
        workspace_id="workspace-a",
        runner=FakeRunner(alive_execution_ids=set()),
    )

    assert reconciled == 1
    await reconciliation_session.refresh(thread)
    assert thread.status == ThreadStatus.ERROR.value
    assert thread.active_turn_execution_id is None
    assert thread.error_code == "runtime_restarted"
    assert thread.error_info == {"active_execution_id": "missing-execution"}


@pytest.mark.asyncio
async def test_reconcile_keeps_queued_thread_with_reserved_execution_alive(
    reconciliation_session: AsyncSession,
) -> None:
    thread = await create_thread(
        reconciliation_session,
        thread_id="reserved-thread",
        status=ThreadStatus.QUEUED,
        active_turn_execution_id="reserved-execution",
    )
    await reconciliation_session.commit()

    reconciled = await reconcile_stale_running_threads(
        reconciliation_session,
        workspace_id="workspace-a",
        runner=FakeRunner(alive_execution_ids={"reserved-execution"}),
    )

    assert reconciled == 0
    await reconciliation_session.refresh(thread)
    assert thread.status == ThreadStatus.QUEUED.value
    assert thread.active_turn_execution_id == "reserved-execution"
    assert thread.error_code is None
    assert thread.error_info is None


@pytest.mark.asyncio
async def test_reconcile_keeps_working_thread_with_active_pump_alive(
    reconciliation_session: AsyncSession,
) -> None:
    thread = await create_thread(
        reconciliation_session,
        thread_id="active-pump-thread",
        status=ThreadStatus.WORKING,
        active_turn_execution_id="active-pump-execution",
    )
    await reconciliation_session.commit()

    reconciled = await reconcile_stale_running_threads(
        reconciliation_session,
        workspace_id="workspace-a",
        runner=FakeRunner(alive_execution_ids={"active-pump-execution"}),
    )

    assert reconciled == 0
    await reconciliation_session.refresh(thread)
    assert thread.status == ThreadStatus.WORKING.value
    assert thread.active_turn_execution_id == "active-pump-execution"
    assert thread.error_code is None
    assert thread.error_info is None


@pytest.mark.asyncio
async def test_reconcile_does_not_mark_stopping_thread_as_runtime_restart(
    reconciliation_session: AsyncSession,
) -> None:
    thread = await create_thread(
        reconciliation_session,
        thread_id="stopping-thread",
        status=ThreadStatus.STOPPING,
        active_turn_execution_id="missing-execution",
    )
    await reconciliation_session.commit()

    reconciled = await reconcile_stale_running_threads(
        reconciliation_session,
        workspace_id="workspace-a",
        runner=FakeRunner(alive_execution_ids=set()),
    )

    assert reconciled == 0
    await reconciliation_session.refresh(thread)
    assert thread.status == ThreadStatus.STOPPING.value
    assert thread.active_turn_execution_id == "missing-execution"
    assert thread.error_code is None
    assert thread.error_info is None


@pytest.mark.asyncio
async def test_reconcile_rechecks_status_and_active_execution_inside_lock(
    reconciliation_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_snapshot = ThreadModel(
        id="raced-thread",
        workspace_id="workspace-a",
        user_id="user-a",
        origin="user",
        title="Running thread",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
        status=ThreadStatus.WORKING.value,
        queued_messages=[],
        draft_message=None,
        active_turn_execution_id="old-execution",
        archived=False,
    )
    locked_model = ThreadModel(
        id="raced-thread",
        workspace_id="workspace-a",
        user_id="user-a",
        origin="user",
        title="Running thread",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
        status=ThreadStatus.COMPLETE.value,
        queued_messages=[],
        draft_message=None,
        active_turn_execution_id=None,
        archived=False,
    )

    class RacedRepository:
        def __init__(self, db: AsyncSession, workspace_id: str) -> None:
            self.db = db
            self.workspace_id = workspace_id

        async def list_reconcilable_running(self) -> list[ThreadModel]:
            return [stale_snapshot]

        async def locked_update(self, thread_id, mutate):
            mutate(locked_model)
            return locked_model

    monkeypatch.setattr(
        "app.modules.thread.reconciliation.ThreadRepository",
        RacedRepository,
    )

    reconciled = await reconcile_stale_running_threads(
        reconciliation_session,
        workspace_id="workspace-a",
        runner=FakeRunner(alive_execution_ids=set()),
    )

    assert reconciled == 0
    assert locked_model.status == ThreadStatus.COMPLETE.value
    assert locked_model.error_code is None
