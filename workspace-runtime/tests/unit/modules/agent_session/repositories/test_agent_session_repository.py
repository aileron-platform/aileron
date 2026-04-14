from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.agent_session.domain.enums import AgentSessionStatus, AgenticTool
from app.modules.agent_session.repositories.agent_session_repository import AgentSessionRepository


def make_db_result(*, all_values=None, scalar=None, scalar_one_or_none=None):
    scalars = SimpleNamespace(all=lambda: all_values or [])
    return SimpleNamespace(
        scalars=lambda: scalars,
        scalar=lambda: scalar,
        scalar_one_or_none=lambda: scalar_one_or_none,
    )


def make_repo() -> tuple[AgentSessionRepository, SimpleNamespace]:
    db = SimpleNamespace(execute=AsyncMock())
    repo = AgentSessionRepository(db)
    return repo, db


@pytest.mark.asyncio
async def test_find_methods_build_and_return_results() -> None:
    repo, db = make_repo()
    session_model = SimpleNamespace(session_id="s1")
    running_model = SimpleNamespace(session_id="s2")
    db.execute = AsyncMock(
        side_effect=[
            make_db_result(all_values=[session_model]),
            make_db_result(all_values=[running_model]),
            make_db_result(scalar_one_or_none=running_model),
        ]
    )

    by_workspace = await repo.find_by_workspace(
        "ws-1",
        status=AgentSessionStatus.RUNNING,
        agentic_tool=AgenticTool.CLAUDE_CODE,
        archived=False,
        limit=10,
        offset=5,
    )
    by_status = await repo.find_by_status(AgentSessionStatus.RUNNING, limit=5, offset=2)
    running = await repo.find_running_by_workspace("ws-1")

    assert by_workspace == [session_model]
    assert by_status == [running_model]
    assert running is running_model
    assert db.execute.await_count == 3


@pytest.mark.asyncio
async def test_update_and_json_blob_mutations() -> None:
    repo, _ = make_repo()
    session_model = SimpleNamespace(session_id="s1", data='{"tasks":["t1"],"message_count":2}')
    updated = SimpleNamespace(session_id="s1")
    repo.update = AsyncMock(return_value=updated)
    repo.find_by_id = AsyncMock(side_effect=[session_model, session_model, session_model, None])

    changed = await repo.update_status("s1", AgentSessionStatus.RUNNING)
    add_existing = await repo.add_task("s1", "t1")
    add_new = await repo.add_task("s1", "t2")
    incremented = await repo.increment_message_count("s1", 3)
    missing = await repo.increment_message_count("missing")

    assert changed is updated
    assert add_existing is session_model
    assert add_new is updated
    payload = json.loads(repo.update.await_args_list[1].args[1]["data"])
    assert payload["tasks"] == ["t1", "t2"]
    assert incremented is updated
    payload = json.loads(repo.update.await_args_list[2].args[1]["data"])
    assert payload["message_count"] == 5
    assert missing is None


@pytest.mark.asyncio
async def test_context_usage_archive_and_to_entity() -> None:
    repo, _ = make_repo()
    now = datetime.now(UTC)
    session_model = SimpleNamespace(
        session_id="s1",
        created_at=now,
        updated_at=now,
        created_by="user-1",
        status=AgentSessionStatus.IDLE.value,
        agentic_tool=AgenticTool.CLAUDE_CODE.value,
        workspace_id="ws-1",
        ready_for_prompt=True,
        archived=False,
        archived_reason=None,
        data='{"custom_context":{"workspace_path":"/tmp/ws"},"sdk_session_id":"sdk-1"}',
    )
    repo.find_by_id = AsyncMock(return_value=session_model)
    repo.update = AsyncMock(return_value=session_model)

    updated = await repo.update_context_usage("s1", 88, limit=200)
    archived = await repo.archive("s1", reason="manual")
    entity = repo.to_entity(session_model)

    assert updated is session_model
    context_payload = json.loads(repo.update.await_args_list[0].args[1]["data"])
    assert context_payload["current_context_usage"] == 88
    assert context_payload["context_window_limit"] == 200
    assert "last_context_update_at" in context_payload
    assert archived is session_model
    assert repo.update.await_args_list[1].args[1]["status"] == AgentSessionStatus.COMPLETED.value
    assert entity.id == "s1"
    assert entity.workspace_id == "ws-1"
    assert entity.sdk_session_id == "sdk-1"
