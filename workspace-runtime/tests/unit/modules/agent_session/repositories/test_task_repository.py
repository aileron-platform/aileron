from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.agent_session.domain.enums import TaskStatus
from app.modules.agent_session.domain.value_objects import MessageRange
from app.modules.agent_session.repositories.task_repository import TaskRepository


def make_db_result(*, all_values=None, scalar_one_or_none=None):
    scalars = SimpleNamespace(all=lambda: all_values or [])
    return SimpleNamespace(
        scalars=lambda: scalars,
        scalar_one_or_none=lambda: scalar_one_or_none,
    )


def make_repo() -> tuple[TaskRepository, SimpleNamespace]:
    db = SimpleNamespace(execute=AsyncMock())
    repo = TaskRepository(db)
    return repo, db


@pytest.mark.asyncio
async def test_find_methods_and_start_task() -> None:
    repo, db = make_repo()
    task1 = SimpleNamespace(task_id="t1")
    task2 = SimpleNamespace(task_id="t2")
    db.execute = AsyncMock(
        side_effect=[
            make_db_result(all_values=[task1]),
            make_db_result(all_values=[task2]),
            make_db_result(scalar_one_or_none=task1),
        ]
    )
    repo.update = AsyncMock(return_value=task1)

    by_session = await repo.find_by_session("s1", status=[TaskStatus.CREATED, TaskStatus.RUNNING], limit=10, offset=2)
    by_status = await repo.find_by_status(TaskStatus.RUNNING)
    active = await repo.find_active_by_session("s1")
    started = await repo.start_task("t1")

    assert by_session == [task1]
    assert by_status == [task2]
    assert active is task1
    assert started is task1
    assert repo.update.await_args.args[1]["status"] == TaskStatus.RUNNING.value


@pytest.mark.asyncio
async def test_complete_fail_stop_and_permission_updates() -> None:
    repo, _ = make_repo()
    now = datetime.now(UTC)
    started_at = now - timedelta(seconds=2)
    task_model = SimpleNamespace(task_id="t1", started_at=started_at, data='{"x":1}')
    repo.find_by_id = AsyncMock(side_effect=[task_model, task_model, task_model, task_model, task_model, None])
    repo.update = AsyncMock(return_value=task_model)

    completed = await repo.complete_task("t1", raw_sdk_response={"ok": True}, computed_context_window=88, completed_at=now)
    failed = await repo.fail_task("t1", error_message="boom", completed_at=now)
    stopped = await repo.stop_task("t1", completed_at=now)
    awaiting = await repo.set_awaiting_permission("t1", {"request_id": "r1"})
    ranged = await repo.update_message_range(
        "t1",
        MessageRange(start_index=1, end_index=3, start_timestamp="2025-01-01T00:00:00Z"),
    )
    missing = await repo.increment_tool_use_count("missing")

    assert completed is task_model
    complete_payload = json.loads(repo.update.await_args_list[0].args[1]["data"])
    assert complete_payload["raw_sdk_response"] == {"ok": True}
    assert complete_payload["computed_context_window"] == 88
    assert complete_payload["duration_ms"] >= 2000
    assert failed is task_model
    fail_payload = json.loads(repo.update.await_args_list[1].args[1]["data"])
    assert fail_payload["error_message"] == "boom"
    assert stopped is task_model
    stop_payload = json.loads(repo.update.await_args_list[2].args[1]["data"])
    assert stop_payload["duration_ms"] >= 2000
    assert awaiting is task_model
    awaiting_payload = json.loads(repo.update.await_args_list[3].args[1]["data"])
    assert awaiting_payload["permission_request"] == {"request_id": "r1"}
    assert ranged is task_model
    range_payload = json.loads(repo.update.await_args_list[4].args[1]["data"])
    assert range_payload["message_range"] == {
        "start_index": 1,
        "end_index": 3,
        "start_timestamp": "2025-01-01T00:00:00Z",
    }
    assert missing is None


@pytest.mark.asyncio
async def test_increment_tool_use_and_to_entity() -> None:
    repo, _ = make_repo()
    now = datetime.now(UTC)
    task_model = SimpleNamespace(
        task_id="t1",
        session_id="s1",
        created_at=now,
        created_by="user-1",
        started_at=now,
        completed_at=None,
        status=TaskStatus.RUNNING.value,
        data='{"tool_use_count":2,"message_range":{"start_index":1,"end_index":2,"start_timestamp":"2025-01-01T00:00:00Z"}}',
    )
    repo.find_by_id = AsyncMock(return_value=task_model)
    repo.update = AsyncMock(return_value=task_model)

    updated = await repo.increment_tool_use_count("t1", 3)
    entity = repo.to_entity(task_model)

    assert updated is task_model
    payload = json.loads(repo.update.await_args.args[1]["data"])
    assert payload["tool_use_count"] == 5
    assert entity.id == "t1"
    assert entity.session_id == "s1"
    assert entity.message_range.start_index == 1
    assert entity.message_range.end_index == 2
