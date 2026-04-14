from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, PermissionUpdate, ToolPermissionContext

from app.modules.agent_session.services.tools.claude.permission_hooks import PermissionHooks


class FakeSignal:
    def __init__(self, aborted: bool = False) -> None:
        self.aborted = aborted
        self.listeners: list = []

    def add_abort_listener(self, callback) -> None:
        self.listeners.append(callback)

    def remove_abort_listener(self, callback) -> None:
        if callback in self.listeners:
            self.listeners.remove(callback)

    def abort(self) -> None:
        self.aborted = True
        for callback in list(self.listeners):
            callback()


@pytest.mark.asyncio
async def test_can_use_tool_user_input_returns_updated_answers() -> None:
    emitted: list[tuple[str, dict]] = []
    hooks = PermissionHooks("session-1", "task-1", lambda name, payload: emitted.append((name, payload)))
    hooks._set_awaiting_permission = AsyncMock()
    hooks._create_permission_message = AsyncMock()
    hooks._wait_for_decision = AsyncMock(return_value={"content": "q0: Alice"})
    hooks._resume_from_permission = AsyncMock()
    context = ToolPermissionContext()
    context.tool_use_id = "tool-use-1"

    result = await hooks.can_use_tool(
        "AskUserQuestion",
        {"questions": [{"question": "What is your name?"}]},
        context,
    )

    assert isinstance(result, PermissionResultAllow)
    assert result.updated_input == {
        "questions": [{"question": "What is your name?"}],
        "answers": {"What is your name?": "Alice"},
    }
    hooks._set_awaiting_permission.assert_awaited_once()
    hooks._create_permission_message.assert_awaited_once()
    hooks._resume_from_permission.assert_awaited_once()
    assert emitted[0][0] == "tool-decision:request"
    assert emitted[0][1]["decision_type"] == "user_input"
    assert hooks._request_options == {}


@pytest.mark.asyncio
async def test_can_use_tool_user_input_timeout_and_aborted_signal_return_deny() -> None:
    emitted: list[tuple[str, dict]] = []
    hooks = PermissionHooks("session-1", "task-1", lambda name, payload: emitted.append((name, payload)))
    hooks._set_awaiting_permission = AsyncMock()
    hooks._create_permission_message = AsyncMock()
    hooks._wait_for_decision = AsyncMock(side_effect=asyncio.TimeoutError())
    hooks._handle_timeout = AsyncMock()

    timeout_result = await hooks.can_use_tool(
        "AskUserQuestion",
        {"questions": [{"question": "Q1"}]},
        ToolPermissionContext(),
    )
    aborted_result = await hooks.can_use_tool(
        "AskUserQuestion",
        {"questions": [{"question": "Q1"}]},
        ToolPermissionContext(signal=SimpleNamespace(aborted=True)),
    )

    assert isinstance(timeout_result, PermissionResultDeny)
    assert "timed out" in timeout_result.message
    hooks._handle_timeout.assert_awaited_once()
    assert isinstance(aborted_result, PermissionResultDeny)
    assert aborted_result.message == "Request cancelled"


@pytest.mark.asyncio
async def test_can_use_tool_permission_flow_supports_updates_deny_and_aborted_signal() -> None:
    emitted: list[tuple[str, dict]] = []
    hooks = PermissionHooks("session-1", "task-1", lambda name, payload: emitted.append((name, payload)))
    hooks._create_permission_message = AsyncMock()
    hooks._set_awaiting_permission = AsyncMock()
    hooks._wait_for_decision = AsyncMock(
        side_effect=[
            {"allow": True, "scope": "project"},
            {"outcome": "cancelled", "reason": "nope"},
        ]
    )
    context = ToolPermissionContext(
        suggestions=[
            PermissionUpdate(
                type="addRules",
                rules=[{"tool_name": "Bash"}],
                behavior="allow",
                destination="projectSettings",
            )
        ]
    )
    context.tool_use_id = "tool-use-1"

    allow_result = await hooks.can_use_tool("Bash", {"command": "ls"}, context)
    deny_result = await hooks.can_use_tool("Bash", {"command": "rm"}, ToolPermissionContext())
    aborted_result = await hooks.can_use_tool(
        "Bash",
        {"command": "pwd"},
        ToolPermissionContext(signal=SimpleNamespace(aborted=True)),
    )

    assert isinstance(allow_result, PermissionResultAllow)
    assert allow_result.updated_input == {"command": "ls"}
    assert allow_result.updated_permissions[0].destination == "projectSettings"
    assert isinstance(deny_result, PermissionResultDeny)
    assert deny_result.message == "nope"
    assert isinstance(aborted_result, PermissionResultDeny)
    assert aborted_result.message == "Request cancelled"
    assert emitted[0][0] == "tool-decision:request"
    assert emitted[0][1]["suggestions"] == [
        {
            "type": "addRules",
            "rules": [{"tool_name": "Bash"}],
            "behavior": "allow",
            "destination": "projectSettings",
        }
    ]
    assert hooks._request_options == {}


@pytest.mark.asyncio
async def test_wait_for_decision_supports_resolve_signal_cancel_and_timeout() -> None:
    hooks = PermissionHooks("session-1", "task-1", lambda *_: None)

    async def resolve_later() -> None:
        await asyncio.sleep(0)
        assert hooks.resolve_decision({"request_id": "req-1", "allow": True, "scope": "session"}) is True

    resolver = asyncio.create_task(resolve_later())
    decision = await hooks._wait_for_decision("req-1", timeout=1)
    await resolver

    signal = FakeSignal()
    wait_task = asyncio.create_task(hooks._wait_for_decision("req-2", timeout=1, signal=signal))
    await asyncio.sleep(0)
    signal.abort()
    cancelled = await wait_task

    with pytest.raises(asyncio.TimeoutError):
        await hooks._wait_for_decision("req-3", timeout=0)

    assert decision == {"request_id": "req-1", "allow": True, "scope": "session"}
    assert cancelled == {"allow": False, "reason": "Cancelled", "decided_by": "system"}
    assert hooks.resolve_decision({"allow": True}) is False
    assert hooks.resolve_decision({"request_id": "missing", "allow": True}) is False


def test_build_input_resolve_decision_and_serialize_helpers() -> None:
    hooks = PermissionHooks("session-1", "task-1", lambda *_: None)
    hooks._request_options["req-1"] = [dict(option) for option in hooks.DEFAULT_PERMISSION_OPTIONS]

    json_input = hooks._build_ask_user_question_input(
        "AskUserQuestion",
        {"questions": [{"question": "Q1"}]},
        '{"q0":"A1"}',
    )
    text_input = hooks._build_ask_user_question_input(
        "AskUserQuestion",
        {"questions": [{"question": "Q1"}, {"question": "Q2"}]},
        "q0: A1\nq1: A2",
    )
    passthrough = hooks._build_ask_user_question_input("OtherTool", {}, "answer")

    assert json_input == {"questions": [{"question": "Q1"}], "answers": {"Q1": "A1"}}
    assert text_input == {
        "questions": [{"question": "Q1"}, {"question": "Q2"}],
        "answers": {"Q1": "A1", "Q2": "A2"},
    }
    assert passthrough == {"answer": "answer"}
    assert hooks._resolve_permission_decision({"allow": True, "scope": "local"}, "req-1") == (True, "local")
    assert hooks._resolve_permission_decision({"option_id": "reject_once"}, "req-1") == (False, "once")
    assert hooks._resolve_permission_decision({"option_id": "allow_session"}, "req-1") == (True, "session")
    assert hooks._resolve_permission_decision({"outcome": "cancelled"}, "req-1") == (False, None)
    assert hooks._serialize_suggestions(
        [
            PermissionUpdate(
                type="addRules",
                rules=[{"tool_name": "Read"}],
                behavior="allow",
                destination="localSettings",
            ),
            {"type": "setMode", "mode": "plan"},
            object(),
        ]
    ) == [
        {
            "type": "addRules",
            "rules": [{"tool_name": "Read"}],
            "behavior": "allow",
            "destination": "localSettings",
        },
        {"type": "setMode", "mode": "plan"},
        {},
    ]


@pytest.mark.asyncio
async def test_handle_timeout_emits_event_and_fails_task() -> None:
    emitted: list[tuple[str, dict]] = []
    hooks = PermissionHooks("session-1", "task-1", lambda name, payload: emitted.append((name, payload)))
    hooks._fail_task = AsyncMock()

    await hooks._handle_timeout("req-1")

    assert emitted == [
        (
            "tool-decision:timeout",
            {"request_id": "req-1", "session_id": "session-1", "task_id": "task-1"},
        )
    ]
    hooks._fail_task.assert_awaited_once_with("Permission request timed out")
