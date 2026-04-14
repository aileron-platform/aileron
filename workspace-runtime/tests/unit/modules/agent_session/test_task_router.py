from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.agent_session.domain.enums import TaskStatus
from app.modules.agent_session.schemas.task import TaskCreate
from app.modules.agent_session.services.task_service import InvalidStateTransitionError, TaskServiceError

router_module = importlib.import_module("app.modules.agent_session.routers.task_router")


@pytest.mark.asyncio
async def test_task_router_crud_and_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AsyncMock()
    execution_service = AsyncMock()
    task = SimpleNamespace(id="task-1", status=TaskStatus.STOPPING)
    service.create_task.return_value = task
    service.get_task.side_effect = [task, None]
    service.find_tasks.return_value = ([task], 1)
    service.stop_task.return_value = task

    monkeypatch.setattr(
        router_module.TaskResponse,
        "from_entity",
        classmethod(
            lambda cls, entity: cls(
                id=entity.id,
                session_id="session-1",
                created_at=datetime.now(timezone.utc),
                status=entity.status,
            )
        ),
    )

    created = await router_module.create_task("session-1", TaskCreate(session_id="ignored", full_prompt="run"), service)
    fetched = await router_module.get_task("session-1", "task-1", service)
    listed = await router_module.list_tasks("session-1", TaskStatus.RUNNING, 10, 0, service)
    stopped = await router_module.stop_task("session-1", "task-1", service, execution_service)

    assert created.task_id == "task-1"
    assert fetched.task_id == "task-1"
    assert listed.total == 1
    assert listed.items[0].task_id == "task-1"
    assert stopped.task_id == "task-1"

    with pytest.raises(HTTPException) as exc_get:
        await router_module.get_task("session-1", "missing", service)
    assert exc_get.value.status_code == 404

    execution_service.stop_task.side_effect = RuntimeError("sdk stop failed")
    await router_module.stop_task("session-1", "task-1", service, execution_service)

    service.stop_task.side_effect = TaskServiceError("missing task")
    with pytest.raises(HTTPException) as exc_stop_missing:
        await router_module.stop_task("session-1", "missing", service, execution_service)
    assert exc_stop_missing.value.status_code == 404

    service.stop_task.side_effect = InvalidStateTransitionError("cannot stop")
    with pytest.raises(HTTPException) as exc_stop_invalid:
        await router_module.stop_task("session-1", "task-1", service, execution_service)
    assert exc_stop_invalid.value.status_code == 404
