from __future__ import annotations

import importlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.agent_session.domain.enums import MessageStatus, PermissionMode, ToolDecisionOutcome, ToolDecisionType
from app.modules.agent_session.schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionUpdate,
    PromptRequest,
    ToolDecisionRequest,
    ToolResultRequest,
)
from app.modules.agent_session.services.execution_service import ExecutionServiceError
from app.modules.version_control.utils import VersionControlError

router_module = importlib.import_module("app.modules.agent_session.routers.agent_session_router")


@pytest.mark.asyncio
async def test_session_crud_and_listing_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AsyncMock()
    session = SimpleNamespace(id="session-1")
    service.create_session.return_value = session
    service.get_session.side_effect = [session, None]
    service.find_sessions.return_value = ([session], 1)
    service.update_session.side_effect = [session, None]
    service.delete_session.side_effect = [True, False]
    service.archive_session.side_effect = [session, None]

    monkeypatch.setattr(
        router_module.AgentSessionResponse,
        "from_entity",
            classmethod(
                lambda cls, entity: cls(
                    session_id=entity.id,
                    created_at=datetime.now(timezone.utc),
                    status="idle",
                    agentic_tool="claude-code",
                    workspace_id="ws-1",
                )
        ),
    )
    mock_db = AsyncMock()

    @asynccontextmanager
    async def fake_scope():
        yield mock_db

    monkeypatch.setattr(router_module, "async_session_scope", fake_scope)
    monkeypatch.setattr(router_module, "AgentSessionService", lambda db: service)

    created = await router_module.create_session(AgentSessionCreate(workspace_id="ws-1"))
    fetched = await router_module.get_session("session-1", service)
    listed = await router_module.list_sessions("ws-1", None, None, None, False, 10, 0, service)
    updated = await router_module.update_session("session-1", AgentSessionUpdate(title="new"), service)
    await router_module.delete_session("session-1", service)
    archived = await router_module.archive_session("session-1", "manual", service)

    assert created.session_id == "session-1"
    service.create_session.assert_awaited_once()
    assert fetched.session_id == "session-1"
    assert listed.total == 1
    assert listed.items[0].session_id == "session-1"
    assert updated.session_id == "session-1"
    assert archived.session_id == "session-1"

    with pytest.raises(HTTPException) as exc_get:
        await router_module.get_session("missing", service)
    assert exc_get.value.status_code == 404

    with pytest.raises(HTTPException) as exc_update:
        await router_module.update_session("missing", AgentSessionUpdate(title="x"), service)
    assert exc_update.value.status_code == 404

    with pytest.raises(HTTPException) as exc_delete:
        await router_module.delete_session("missing", service)
    assert exc_delete.value.status_code == 404

    with pytest.raises(HTTPException) as exc_archive:
        await router_module.archive_session("missing", "manual", service)
    assert exc_archive.value.status_code == 404


@pytest.mark.asyncio
async def test_create_session_maps_version_control_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AsyncMock()
    service.create_session.side_effect = VersionControlError(
        "Git context 'missing' not found",
        status_code=404,
        error_code="VC_CONTEXT_NOT_FOUND",
    )
    mock_db = AsyncMock()

    @asynccontextmanager
    async def fake_scope():
        yield mock_db

    monkeypatch.setattr(router_module, "async_session_scope", fake_scope)
    monkeypatch.setattr(router_module, "AgentSessionService", lambda db: service)

    with pytest.raises(HTTPException) as exc_info:
        await router_module.create_session(
            AgentSessionCreate(workspace_id="ws-1", git_context_id="missing")
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_execute_prompt_maps_execution_errors() -> None:
    execution_service = AsyncMock()
    execution_service.execute_prompt.return_value = {
        "success": True,
        "task_id": "task-1",
        "status": "running",
        "streaming": True,
        "queued": False,
    }

    result = await router_module.execute_prompt(
        "session-1",
        PromptRequest(prompt="hello", stream=True, permission_mode=PermissionMode.DEFAULT),
        execution_service,
    )
    assert result.task_id == "task-1"
    assert result.status == "running"

    for message, expected_status in [
        ("Session not found: missing", 404),
        ("session has active task", 409),
        ("bad request", 400),
    ]:
        execution_service.execute_prompt.side_effect = ExecutionServiceError(message)
        with pytest.raises(HTTPException) as exc_info:
            await router_module.execute_prompt("session-1", PromptRequest(prompt="hello"), execution_service)
        assert exc_info.value.status_code == expected_status


@pytest.mark.asyncio
async def test_handle_tool_decision_and_submit_tool_result(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_decision_service = AsyncMock()
    tool_decision_service.resolve_decision.return_value = True

    class DecisionManager:
        def resolve_decision(self, session_id: str, data: dict) -> bool:
            assert session_id == "session-1"
            return True

        def resolve_tool_input(self, session_id: str, data: dict) -> bool:
            assert data["tool_use_id"] == "tool-1"
            return False

    monkeypatch.setattr(
        "app.modules.agent_session.services.tool_decision_manager.global_tool_decision_manager",
        DecisionManager(),
    )

    decision_result = await router_module.handle_tool_decision(
        "session-1",
        ToolDecisionRequest(
            request_id="req-1",
            task_id="task-1",
            decision_type=ToolDecisionType.PERMISSION,
            outcome=ToolDecisionOutcome.SELECTED,
            option_id="allow_once",
            decided_by="user-1",
        ),
        tool_decision_service,
    )
    tool_result = await router_module.submit_tool_result(
        "session-1",
        ToolResultRequest(tool_use_id="tool-1", task_id="task-1", content="answer"),
        AsyncMock(),
    )

    assert decision_result.success is True
    assert decision_result.hooks_resolved is True
    assert tool_result["hooks_resolved"] is False

    tool_decision_service.resolve_decision.side_effect = RuntimeError("boom")
    with pytest.raises(HTTPException) as exc_info:
        await router_module.handle_tool_decision(
            "session-1",
            ToolDecisionRequest(
                request_id="req-2",
                task_id="task-1",
                decision_type=ToolDecisionType.PERMISSION,
                outcome=ToolDecisionOutcome.CANCELLED,
                decided_by="user-1",
            ),
            tool_decision_service,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_queued_message_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    queued_message = SimpleNamespace(
        id="msg-1",
        session_id="session-1",
        status=MessageStatus.QUEUED,
        queue_position=2,
        content_preview="queued canvas",
        created_at=datetime.now(timezone.utc),
    )
    dispatching_message = SimpleNamespace(
        id="msg-2",
        session_id="session-1",
        status=MessageStatus.DISPATCHING,
        queue_position=1,
        content_preview="dispatching canvas",
        created_at=datetime.now(timezone.utc),
    )
    message_service = AsyncMock()
    message_service.get_message.side_effect = [queued_message, None, dispatching_message]
    message_service.delete_queued_message.side_effect = [True, False]
    emitter = AsyncMock()
    db = AsyncMock()

    monkeypatch.setattr("app.modules.agent_session.services.message_service.MessageService", lambda _: message_service)
    monkeypatch.setattr("app.modules.agent_session.websocket.events.get_event_emitter", lambda: emitter)

    await router_module.delete_queued_message("session-1", "msg-1", db)
    # commit is automatically managed by session.begin() from get_async_db, no need to manually await db.commit()
    emitter.emit.assert_awaited_once()

    with pytest.raises(HTTPException) as exc_missing:
        await router_module.delete_queued_message("session-1", "missing", db)
    assert exc_missing.value.status_code == 404

    with pytest.raises(HTTPException) as exc_dispatching:
        await router_module.delete_queued_message("session-1", "msg-2", db)
    assert exc_dispatching.value.status_code == 409

    message_service.get_queued_messages.return_value = [queued_message]
    result = await router_module.get_queued_messages("session-1", AsyncMock())
    assert result["count"] == 1
    assert result["messages"][0]["message_id"] == "msg-1"
    assert result["messages"][0]["status"] == "queued"
