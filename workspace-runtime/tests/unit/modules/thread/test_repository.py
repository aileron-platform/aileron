from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.thread.persistence_models import Base, ThreadModel
from app.modules.thread.message_repository import (
    ThreadMessageRepository,
)
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.turn_repository import ThreadTurnRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def thread_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    async with postgres_engine.begin() as connection:
        await connection.execute(
            text("DROP TABLE IF EXISTS thread_tool_result_contents CASCADE")
        )
        await connection.execute(text("DROP TABLE IF EXISTS thread_messages CASCADE"))
        await connection.execute(
            text("DROP TABLE IF EXISTS thread_turn_executions CASCADE")
        )
        await connection.execute(text("DROP TABLE IF EXISTS thread_turns CASCADE"))
        await connection.execute(text("DROP TABLE IF EXISTS threads CASCADE"))
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(postgres_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


def thread_model(
    thread_id: str,
    *,
    workspace_id: str = "workspace-a",
    user_id: str = "user-a",
    origin: str = "user",
    automation_execution_id: str | None = None,
) -> ThreadModel:
    return ThreadModel(
        id=thread_id,
        workspace_id=workspace_id,
        user_id=user_id,
        origin=origin,
        automation_execution_id=automation_execution_id,
        title="Thread",
        agentic_tool="claude",
        model="model-a",
        status="draft",
        version=0,
        queued_messages=[],
        archived=False,
    )


async def test_automation_thread_lookup_is_idempotent_and_workspace_scoped(
    thread_session: AsyncSession,
) -> None:
    repo = ThreadRepository(thread_session, "workspace-a")
    first = await repo.create_or_get_automation(
        thread_model(
            "thread-a",
            origin="automation",
            automation_execution_id="execution-a",
        )
    )
    second = await repo.create_or_get_automation(
        thread_model(
            "thread-b",
            origin="automation",
            automation_execution_id="execution-a",
        )
    )

    assert first.id == second.id == "thread-a"
    assert (
        await ThreadRepository(
            thread_session, "workspace-b"
        ).get_by_automation_execution("execution-a")
        is None
    )


async def test_user_mutation_lookup_and_workspace_read_lookup_are_separate(
    thread_session: AsyncSession,
) -> None:
    repo = ThreadRepository(thread_session, "workspace-a")
    await repo.create(thread_model("user-thread"))
    await repo.create(
        thread_model(
            "automation-thread",
            origin="automation",
            automation_execution_id="execution-a",
        )
    )

    assert await repo.get("user-thread", "user-a") is not None
    assert await repo.get("user-thread", "user-b") is None
    assert await repo.get("automation-thread", "user-a") is None
    assert await repo.get_readable("automation-thread", "workspace-viewer") is not None


async def test_timeline_page_uses_exclusive_message_sequence_cursor(
    thread_session: AsyncSession,
) -> None:
    thread_repo = ThreadRepository(thread_session, "workspace-a")
    turn_repo = ThreadTurnRepository(thread_session)
    thread = await thread_repo.create(thread_model("thread-a"))
    turn = await turn_repo.create_turn(
        thread=thread, turn_id="turn-a", status="running"
    )
    execution = await turn_repo.create_execution(
        thread=thread,
        turn=turn,
        execution_id="execution-a",
        agentic_tool="claude",
        status="running",
    )
    message_repo = ThreadMessageRepository(thread_session)
    for index in range(1, 7):
        await message_repo.append(
            thread.id,
            turn.id,
            execution.id,
            "agent_text",
            {"parts": [{"type": "text", "text": str(index)}]},
            source_event_key=f"event-{index}",
        )

    latest = await message_repo.list_timeline_anchors(
        "thread-a", before_sequence=None, limit=3
    )
    older = await message_repo.list_timeline_anchors(
        "thread-a", before_sequence=latest[0].message_sequence, limit=3
    )

    assert [message.message_sequence for message in latest] == [4, 5, 6]
    assert [message.message_sequence for message in older] == [1, 2, 3]


async def test_messages_are_scoped_to_turn_and_execution(
    thread_session: AsyncSession,
) -> None:
    thread_repo = ThreadRepository(thread_session, "workspace-a")
    turn_repo = ThreadTurnRepository(thread_session)
    message_repo = ThreadMessageRepository(thread_session)
    thread = await thread_repo.create(thread_model("thread-a"))
    turn = await turn_repo.create_turn(
        thread=thread, turn_id="turn-a", status="running"
    )
    execution = await turn_repo.create_execution(
        thread=thread,
        turn=turn,
        execution_id="execution-a",
        agentic_tool="claude",
        status="running",
    )
    call = await message_repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_call",
        {"name": "Bash", "parameters": {"command": "pwd"}},
        source_event_key="call-event",
        tool_call_key="call-a",
    )
    result = await message_repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_result",
        {
            "isError": False,
            "preview": "ok",
            "byteLength": 2,
            "lineCount": 1,
            "truncated": False,
            "mediaType": "text/plain; charset=utf-8",
        },
        source_event_key="result-event",
        parent_tool_use_id=call.id,
        result_kind="provider_result",
    )

    assert result.parent_tool_use_id == call.id
    assert await message_repo.list_timeline_anchors(
        thread.id, before_sequence=None, limit=10
    ) == [call]
    assert await message_repo.list_results_for_parents(thread.id, [call.id]) == [result]
    assert await message_repo.find_tool_call(execution.id, "call-a") == call


async def test_concurrent_appends_allocate_unique_thread_sequences(
    thread_session: AsyncSession,
    postgres_engine,
) -> None:
    thread_repo = ThreadRepository(thread_session, "workspace-a")
    turn_repo = ThreadTurnRepository(thread_session)
    thread = await thread_repo.create(thread_model("thread-concurrent"))
    turn = await turn_repo.create_turn(
        thread=thread, turn_id="turn-concurrent", status="running"
    )
    execution = await turn_repo.create_execution(
        thread=thread,
        turn=turn,
        execution_id="execution-concurrent",
        agentic_tool="claude",
        status="running",
    )
    await thread_session.commit()
    factory = async_sessionmaker(postgres_engine, expire_on_commit=False)

    async def append(index: int) -> None:
        async with factory() as session:
            await ThreadMessageRepository(session).append(
                thread.id,
                turn.id,
                execution.id,
                "agent_text",
                {"parts": [{"type": "text", "text": str(index)}]},
                source_event_key=f"concurrent-{index}",
            )
            await session.commit()

    await asyncio.gather(*(append(index) for index in range(10)))

    async with factory() as session:
        anchors = await ThreadMessageRepository(session).list_timeline_anchors(
            thread.id, before_sequence=None, limit=20
        )
    assert [message.message_sequence for message in anchors] == list(range(1, 11))


async def test_tool_result_kinds_are_prepaired_and_idempotent(
    thread_session: AsyncSession,
) -> None:
    thread = await ThreadRepository(thread_session, "workspace-a").create(
        thread_model("thread-results")
    )
    turn_repo = ThreadTurnRepository(thread_session)
    turn = await turn_repo.create_turn(
        thread=thread, turn_id="turn-results", status="running"
    )
    execution = await turn_repo.create_execution(
        thread=thread,
        turn=turn,
        execution_id="execution-results",
        agentic_tool="claude",
        status="running",
    )
    repo = ThreadMessageRepository(thread_session)
    call = await repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_call",
        {"name": "Question", "parameters": {}},
        source_event_key="call",
        tool_call_key="call",
    )
    provider = await repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_result",
        {"preview": "delivered"},
        source_event_key="provider-1",
        parent_tool_use_id=call.id,
        result_kind="provider_result",
    )
    replay = await repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_result",
        {"preview": "delivered"},
        source_event_key="provider-2",
        parent_tool_use_id=call.id,
        result_kind="provider_result",
    )
    answer = await repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_result",
        {"preview": '{"answers":{}}'},
        source_event_key="answer",
        parent_tool_use_id=call.id,
        result_kind="interaction_answer",
    )

    assert replay.id == provider.id
    assert answer.id != provider.id
    with pytest.raises(ValueError, match="source_event_key_conflict"):
        await repo.append(
            thread.id,
            turn.id,
            execution.id,
            "tool_result",
            {"preview": "different"},
            source_event_key="provider-3",
            parent_tool_use_id=call.id,
            result_kind="provider_result",
        )
