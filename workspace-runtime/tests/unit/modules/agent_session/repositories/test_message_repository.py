from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.agent_session.domain.enums import MessageStatus, MessageType
from app.modules.agent_session.repositories.message_repository import MessageRepository


def make_db_result(*, all_values=None, scalar=None, rowcount=0):
    scalars = SimpleNamespace(all=lambda: all_values or [])
    return SimpleNamespace(
        scalars=lambda: scalars,
        scalar=lambda: scalar,
        rowcount=rowcount,
    )


def make_repo() -> tuple[MessageRepository, SimpleNamespace]:
    db = SimpleNamespace(execute=AsyncMock(), add=lambda instance: None, flush=AsyncMock(), refresh=AsyncMock())
    repo = MessageRepository(db)
    return repo, db


@pytest.mark.asyncio
async def test_find_and_index_methods_return_expected_rows() -> None:
    repo, db = make_repo()
    msg1 = SimpleNamespace(message_id="m1")
    msg2 = SimpleNamespace(message_id="m2")
    db.execute = AsyncMock(
        side_effect=[
            make_db_result(all_values=[msg1]),
            make_db_result(all_values=[msg2]),
            make_db_result(all_values=[msg1, msg2]),
            make_db_result(scalar=4),
        ]
    )

    by_session = await repo.find_by_session("s1", task_id="t1", message_type=MessageType.USER, limit=10, offset=1)
    by_task = await repo.find_by_task("t1")
    by_range = await repo.find_by_range("s1", 1, 3)
    next_index = await repo.get_next_index("s1")

    assert by_session == [msg1]
    assert by_task == [msg2]
    assert by_range == [msg1, msg2]
    assert next_index == 5


@pytest.mark.asyncio
async def test_create_bulk_delete_and_queue_methods() -> None:
    repo, db = make_repo()
    db.execute = AsyncMock(
        side_effect=[
            make_db_result(rowcount=2),
            make_db_result(scalar=2),
            make_db_result(all_values=[SimpleNamespace(message_id="q1"), SimpleNamespace(message_id="q2")]),
            make_db_result(all_values=[SimpleNamespace(message_id="q1"), SimpleNamespace(message_id="q2")]),
            make_db_result(all_values=[SimpleNamespace(message_id="q1", status=MessageStatus.QUEUED.value)]),
            make_db_result(rowcount=1),
            make_db_result(rowcount=1),
            make_db_result(rowcount=1),
            make_db_result(scalar=1),
        ]
    )

    created = await repo.create_bulk(
        [
            {
                "message_id": "m1",
                "session_id": "s1",
                "task_id": None,
                "type": "user",
                "role": "user",
                "index": 0,
            },
            {
                "message_id": "m2",
                "session_id": "s1",
                "task_id": None,
                "type": "assistant",
                "role": "assistant",
                "index": 1,
            },
        ]
    )
    deleted = await repo.delete_by_session("s1")
    queued = await repo.create_queued("s1", "hello", metadata={"a": 1})
    found = await repo.find_queued("s1")
    next_queued = await repo.get_next_queued("s1")
    claimed = await repo.claim_next_queued("s1")
    removed = await repo.delete_queued("q1")
    removed_dispatching = await repo.delete_dispatching("q1")
    queued_count = await repo.count_queued("s1")

    assert len(created) == 2
    db.flush.assert_awaited()
    assert deleted == 2
    assert queued.status == MessageStatus.QUEUED.value
    assert queued.queue_position == 3
    assert found[0].message_id == "q1"
    assert next_queued.message_id == "q1"
    assert claimed.message_id == "q1"
    assert claimed.status == MessageStatus.DISPATCHING.value
    assert removed is True
    assert removed_dispatching is True
    assert queued_count == 1


@pytest.mark.asyncio
async def test_permission_request_lookup_and_to_entity() -> None:
    repo, db = make_repo()
    now = datetime.now(UTC)
    match = SimpleNamespace(
        message_id="m1",
        created_at=now,
        session_id="s1",
        task_id="t1",
        type=MessageType.PERMISSION_REQUEST.value,
        role="system",
        index=1,
        timestamp=now,
        content_preview="canvas",
        parent_tool_use_id=None,
        status=None,
        queue_position=None,
        data='{"content":{"request_id":"req-1"},"metadata":{"x":1}}',
    )
    non_match = SimpleNamespace(message_id="m2", data='{"content":{"request_id":"other"}}')
    db.execute = AsyncMock(side_effect=[make_db_result(all_values=[non_match, match]), make_db_result(scalar=0)])

    found = await repo.find_permission_request("s1", "req-1")
    entity = repo.to_entity(match)
    missing = await repo.count_queue("s2")

    assert found is match
    assert entity.id == "m1"
    assert entity.session_id == "s1"
    assert entity.metadata == {"x": 1}
    assert missing == 0
