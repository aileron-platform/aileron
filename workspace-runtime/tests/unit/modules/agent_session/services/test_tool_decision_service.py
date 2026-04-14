from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.agent_session.domain.enums import (
    AgentSessionStatus,
    PermissionScope,
    TaskStatus,
    ToolDecisionOutcome,
    ToolDecisionType,
)
from app.modules.agent_session.schemas.agent_session import ToolDecisionRequest
from app.modules.agent_session.services.tool_decision_service import (
    ToolDecisionService,
    ToolDecisionServiceError,
    ToolDecisionTimeoutError,
)


@pytest.fixture
def tool_decision_service() -> ToolDecisionService:
    return ToolDecisionService(
        db=AsyncMock(),
        session_repo=AsyncMock(),
        task_repo=AsyncMock(),
        message_repo=AsyncMock(),
        event_emitter=Mock(),
    )


@pytest.mark.asyncio
async def test_create_tool_decision_request_updates_task_session_and_emits_event(
    tool_decision_service: ToolDecisionService,
) -> None:
    tool_decision_service._create_permission_message = AsyncMock()

    request_id = await tool_decision_service.create_tool_decision_request(
        session_id="session-1",
        task_id="task-1",
        tool_name="bash",
        tool_input={"cmd": "pwd"},
        tool_use_id="tool-1",
        decision_type="permission",
        options=[{"option_id": "allow", "kind": "allow_once"}],
        tool_call={"title": "bash"},
        tool_call_id="call-1",
        timeout_seconds=30,
    )

    assert request_id in tool_decision_service._session_requests["session-1"]
    tool_decision_service.task_repo.set_awaiting_permission.assert_awaited_once()
    tool_decision_service.session_repo.update_status.assert_awaited_once_with(
        "session-1", AgentSessionStatus.AWAITING_PERMISSION
    )
    tool_decision_service._create_permission_message.assert_awaited_once()
    event_name, payload = tool_decision_service.event_emitter.call_args.args
    assert event_name == "tool-decision:request"
    assert payload["task_id"] == "task-1"
    assert payload["timeout"] == 30


@pytest.mark.asyncio
async def test_wait_for_decision_success_and_timeout_cleanup(
    tool_decision_service: ToolDecisionService,
) -> None:
    decision = ToolDecisionRequest(
        request_id="req-1",
        task_id="task-1",
        decision_type=ToolDecisionType.PERMISSION,
        outcome=ToolDecisionOutcome.SELECTED,
        decided_by="user-1",
    )

    async def resolve_later() -> None:
        await asyncio.sleep(0)
        tool_decision_service._decision_results["req-1"] = decision
        tool_decision_service._pending_decisions["req-1"].set()

    task = asyncio.create_task(resolve_later())
    result = await tool_decision_service.wait_for_decision("req-1", timeout_seconds=1)
    await task

    assert result == decision
    assert "req-1" not in tool_decision_service._pending_decisions
    assert "req-1" not in tool_decision_service._decision_results

    with pytest.raises(ToolDecisionTimeoutError):
        await tool_decision_service.wait_for_decision("req-timeout", timeout_seconds=0.01)

    assert "req-timeout" not in tool_decision_service._pending_decisions


@pytest.mark.asyncio
async def test_resolve_decision_approved_and_denied_paths(
    tool_decision_service: ToolDecisionService,
) -> None:
    tool_decision_service.task_repo.find_by_id.return_value = SimpleNamespace(session_id="session-1")
    tool_decision_service._update_permission_message = AsyncMock()
    tool_decision_service._resolve_decision_outcome = AsyncMock(return_value=(True, "session"))
    tool_decision_service._pending_decisions["req-1"] = asyncio.Event()

    approved_decision = ToolDecisionRequest(
        request_id="req-1",
        task_id="task-1",
        decision_type=ToolDecisionType.PERMISSION,
        outcome=ToolDecisionOutcome.SELECTED,
        option_id="allow",
        decided_by="user-1",
        scope=PermissionScope.SESSION,
    )

    result = await tool_decision_service.resolve_decision(approved_decision)

    assert result is True
    assert tool_decision_service._pending_decisions["req-1"].is_set() is True
    tool_decision_service.task_repo.update.assert_awaited_once_with("task-1", {"status": TaskStatus.RUNNING.value})
    tool_decision_service.session_repo.update_status.assert_awaited_once_with(
        "session-1", AgentSessionStatus.RUNNING
    )

    tool_decision_service.task_repo.update.reset_mock()
    tool_decision_service.session_repo.update_status.reset_mock()
    tool_decision_service.task_repo.fail_task.reset_mock()
    tool_decision_service.cancel_pending_requests = AsyncMock(return_value=1)
    tool_decision_service._resolve_decision_outcome = AsyncMock(return_value=(False, "session"))

    denied_decision = ToolDecisionRequest(
        request_id="req-2",
        task_id="task-1",
        decision_type=ToolDecisionType.PERMISSION,
        outcome=ToolDecisionOutcome.CANCELLED,
        decided_by="user-1",
        reason="no",
    )

    await tool_decision_service.resolve_decision(denied_decision)

    tool_decision_service.task_repo.fail_task.assert_awaited_once_with("task-1", error_message="no")
    tool_decision_service.session_repo.update_status.assert_awaited_once_with(
        "session-1", AgentSessionStatus.IDLE
    )
    tool_decision_service.cancel_pending_requests.assert_awaited_once_with("session-1")


@pytest.mark.asyncio
async def test_resolve_decision_raises_when_task_missing(
    tool_decision_service: ToolDecisionService,
) -> None:
    tool_decision_service.task_repo.find_by_id.return_value = None

    with pytest.raises(ToolDecisionServiceError, match="Task not found"):
        await tool_decision_service.resolve_decision(
            ToolDecisionRequest(
                request_id="req-1",
                task_id="missing-task",
                decision_type=ToolDecisionType.PERMISSION,
                outcome=ToolDecisionOutcome.SELECTED,
                decided_by="user-1",
            )
        )


@pytest.mark.asyncio
async def test_handle_timeout_and_cancel_methods(tool_decision_service: ToolDecisionService) -> None:
    tool_decision_service.task_repo.find_by_id.return_value = SimpleNamespace(session_id="session-1")
    tool_decision_service._update_permission_message = AsyncMock()

    await tool_decision_service.handle_timeout("req-1", "task-1")

    tool_decision_service.task_repo.fail_task.assert_awaited_once_with(
        "task-1", error_message="Tool decision request timed out"
    )
    tool_decision_service.session_repo.update_status.assert_awaited_once_with(
        "session-1", AgentSessionStatus.IDLE
    )
    assert tool_decision_service.event_emitter.call_args.args[0] == "tool-decision:timeout"

    tool_decision_service._pending_decisions["req-2"] = asyncio.Event()
    await tool_decision_service.cancel_request("req-2")
    assert tool_decision_service._pending_decisions["req-2"].is_set() is True
    assert tool_decision_service._decision_results["req-2"].outcome == ToolDecisionOutcome.CANCELLED

    event_one = asyncio.Event()
    event_two = asyncio.Event()
    tool_decision_service._pending_decisions["req-a"] = event_one
    tool_decision_service._pending_decisions["req-b"] = event_two
    tool_decision_service._session_requests["session-1"] = {"req-a", "req-b"}

    cancelled = await tool_decision_service.cancel_pending_requests("session-1")

    assert cancelled == 2
    assert event_one.is_set() and event_two.is_set()
    assert "session-1" not in tool_decision_service._session_requests


@pytest.mark.asyncio
async def test_helper_methods_cover_option_resolution_and_request_content(
    tool_decision_service: ToolDecisionService,
) -> None:
    tool_decision_service.message_repo.find_permission_request.return_value = SimpleNamespace(
        data='{"content":{"options":[{"option_id":"allow","kind":"allow_always"}]}}'
    )

    content = await tool_decision_service._get_request_content("session-1", "req-1")
    assert content["options"][0]["option_id"] == "allow"
    assert tool_decision_service._find_option(content["options"], "allow") == {
        "option_id": "allow",
        "kind": "allow_always",
    }
    assert tool_decision_service._scope_from_option_kind("allow_once") == "once"
    assert tool_decision_service._scope_from_option_kind("allow_always") == "session"
    assert tool_decision_service._scope_from_option_kind("reject_always") == "session"
    assert tool_decision_service._scope_from_option_kind("other") is None

    decision = ToolDecisionRequest(
        request_id="req-1",
        task_id="task-1",
        decision_type=ToolDecisionType.PERMISSION,
        outcome=ToolDecisionOutcome.SELECTED,
        option_id="allow",
        decided_by="user-1",
    )
    approved, scope = await tool_decision_service._resolve_decision_outcome("session-1", "req-1", decision)
    assert approved is True
    assert scope == "session"

    tool_decision_service.message_repo.find_permission_request.return_value = SimpleNamespace(data="bad-json")
    assert await tool_decision_service._get_request_content("session-1", "req-2") == {}
