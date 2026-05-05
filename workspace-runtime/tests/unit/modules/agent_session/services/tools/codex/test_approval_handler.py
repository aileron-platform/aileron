from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest

import app.modules.agent_session.services.tools.codex.approval_handler as module
from app.modules.agent_session.services.tools.codex.approval_handler import (
    CodexApprovalHandler,
    default_decline_response,
)


def test_default_decline_response_is_schema_valid() -> None:
    assert default_decline_response("item/commandExecution/requestApproval") == {
        "decision": "decline"
    }
    assert default_decline_response("item/fileChange/requestApproval") == {
        "decision": "decline"
    }
    assert default_decline_response("item/permissions/requestApproval") == {
        "permissions": {},
        "scope": "turn",
    }
    assert default_decline_response("unknown") == {}


@pytest.mark.parametrize(
    ("option", "outcome", "expected"),
    [
        ({"option_id": "allow_once", "kind": "allow_once", "scope": "once"}, "selected", "accept"),
        (
            {"option_id": "allow_session", "kind": "allow_always", "scope": "session"},
            "selected",
            "acceptForSession",
        ),
        ({"option_id": "reject_once", "kind": "reject_once", "scope": "once"}, "selected", "decline"),
        ({"option_id": "allow_once", "kind": "allow_once", "scope": "once"}, "cancelled", "cancel"),
    ],
)
def test_resolve_decision_maps_option_kind_and_scope(option, outcome, expected) -> None:
    handler = CodexApprovalHandler("session-12345678", "task-1", lambda *_: None, asyncio.new_event_loop())
    event = threading.Event()
    handler._pending["approval-1"] = event
    handler._request_options["approval-1"] = [option]

    assert handler.resolve_decision(
        {
            "request_id": "approval-1",
            "outcome": outcome,
            "option_id": option["option_id"],
            "scope": option["scope"],
        }
    )
    assert handler._results["approval-1"] == expected
    assert event.is_set()


def test_extract_tool_input_shapes() -> None:
    handler = CodexApprovalHandler("session-12345678", "task-1", lambda *_: None, asyncio.new_event_loop())
    assert handler._extract_tool_input(
        "item/commandExecution/requestApproval",
        {"command": "ls", "cwd": "/workspace"},
    ) == {"command": "ls", "cwd": "/workspace"}
    assert handler._extract_tool_input(
        "item/fileChange/requestApproval",
        {"grantRoot": "/workspace/a.py", "reason": "edit"},
    ) == {"path": "/workspace/a.py", "reason": "edit"}
    assert handler._extract_tool_input(
        "item/fileChange/requestApproval",
        {"grantRoot": None, "reason": None},
    ) == {}


def test_permissions_request_returns_without_emit() -> None:
    emitted = []
    handler = CodexApprovalHandler("session-12345678", "task-1", lambda *args: emitted.append(args), asyncio.new_event_loop())

    result = handler.sync_approval_callback("item/permissions/requestApproval", {})

    assert result == {"permissions": {}, "scope": "turn"}
    assert emitted == []


def test_command_approval_timeout_returns_cancel(monkeypatch) -> None:
    emitted = []

    async def fake_request(*_args, **_kwargs):
        return None

    def fake_run_coroutine_threadsafe(coro, *_args, **_kwargs):
        coro.close()
        return SimpleNamespace(result=lambda timeout: None)

    monkeypatch.setattr(module.asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    handler = CodexApprovalHandler(
        "session-12345678",
        "task-1",
        lambda *args: emitted.append(args),
        asyncio.new_event_loop(),
        timeout_seconds=0,
    )
    monkeypatch.setattr(handler, "_request_via_websocket", fake_request)

    result = handler.sync_approval_callback(
        "item/commandExecution/requestApproval",
        {"command": "ls", "cwd": "/workspace"},
    )

    assert result == {"decision": "cancel"}
    assert emitted[0][0] == "tool-decision:timeout"
