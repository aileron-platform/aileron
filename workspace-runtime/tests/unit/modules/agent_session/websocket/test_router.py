from __future__ import annotations

from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import WebSocketDisconnect

from app.modules.agent_session.websocket import router as router_module
from app.services.auth_service import SimpleUser


@pytest.mark.asyncio
async def test_handle_client_message_ping_subscribe_unsubscribe_and_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = AsyncMock()
    manager.subscribe_session.return_value = True
    manager.unsubscribe_session.return_value = True

    class SessionService:
        async def get_session(self, session_id: str):
            return SimpleNamespace(id=session_id)

        @staticmethod
        def _session_to_event_data(session):
            return {"session_id": session.id}

    @asynccontextmanager
    async def fake_scope():
        yield AsyncMock()

    monkeypatch.setattr("app.modules.agent_session.services.agent_session_service.AgentSessionService", SessionService)
    monkeypatch.setattr(router_module, "async_session_scope", fake_scope)
    replay_mock = AsyncMock()
    monkeypatch.setattr(router_module, "_replay_pending_tool_decision", replay_mock)

    await router_module._handle_client_message(manager, "conn-1", {"type": "ping"})
    await router_module._handle_client_message(manager, "conn-1", {"type": "subscribe", "session_id": "session-1"})
    await router_module._handle_client_message(manager, "conn-1", {"type": "subscribe"})
    await router_module._handle_client_message(manager, "conn-1", {"type": "unsubscribe", "session_id": "session-1"})
    await router_module._handle_client_message(manager, "conn-1", {"type": "unsubscribe"})
    await router_module._handle_client_message(manager, "conn-1", {"type": "other"})

    sent_payloads = [call.args[1] for call in manager.send_to_connection.await_args_list]
    assert sent_payloads[0] == {"type": "pong"}
    assert {"type": "subscribed", "session_id": "session-1", "success": True} in sent_payloads
    assert {"type": "unsubscribed", "session_id": "session-1", "success": True} in sent_payloads
    assert {"type": "error", "message": "session_id is required"} in sent_payloads
    assert {"type": "error", "message": "Unknown message type: other"} in sent_payloads
    replay_mock.assert_awaited_once_with(manager, "conn-1", "session-1")


@pytest.mark.asyncio
async def test_replay_pending_tool_decision_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = AsyncMock()

    class TaskRepo:
        def __init__(self, db):
            self.db = db

        async def find_active_by_session(self, session_id: str):
            return SimpleNamespace(
                task_id="task-1",
                status="awaiting_permission",
                data='{"permission_request":{"request_id":"req-1","tool_name":"bash","tool_input":{"cmd":"pwd"},"tool_use_id":"tool-1"}}',
            )

    @asynccontextmanager
    async def fake_scope():
        yield AsyncMock()

    monkeypatch.setattr(router_module, "async_session_scope", fake_scope)
    monkeypatch.setattr("app.modules.agent_session.repositories.task_repository.TaskRepository", TaskRepo)

    await router_module._replay_pending_tool_decision(manager, "conn-1", "session-1")
    payload = manager.send_to_connection.await_args.args[1]
    assert payload["type"] == "tool-decision:request"
    assert payload["data"]["timeout"] == 60

    class UserInputTaskRepo(TaskRepo):
        async def find_active_by_session(self, session_id: str):
            return SimpleNamespace(
                task_id="task-2",
                status="awaiting_permission",
                data='{"permission_request":{"request_id":"req-2","tool_name":"ask","tool_input":{"q":"hi"},"type":"user_input"}}',
            )

    monkeypatch.setattr("app.modules.agent_session.repositories.task_repository.TaskRepository", UserInputTaskRepo)
    await router_module._replay_pending_tool_decision(manager, "conn-1", "session-1")
    payload = manager.send_to_connection.await_args.args[1]
    assert payload["data"]["timeout"] == 300


@pytest.mark.asyncio
async def test_replay_session_events_batches_and_stops_on_send_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = AsyncMock()
    manager.send_to_connection.side_effect = [True, True, False]
    replay_store = AsyncMock()
    replay_store.list_events_since.side_effect = [
        [{"seq": 2, "type": "a"}, {"seq": 3, "type": "b"}],
        [{"seq": 4, "type": "c"}],
    ]
    monkeypatch.setattr(router_module, "get_websocket_replay_store", lambda: replay_store)

    total = await router_module._replay_session_events(manager, "conn-1", "session-1", 1)
    assert total == 2

    manager.send_to_connection.side_effect = [True]
    replay_store.list_events_since.side_effect = [[{"seq": 1, "type": "a"}]]
    total = await router_module._replay_session_events(manager, "conn-1", "session-1", 1)
    assert total == 1


@pytest.mark.asyncio
async def test_websocket_session_endpoint_initializes_replay_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = Mock()
    manager.connect = AsyncMock(return_value="conn-1")
    manager.get_connection_count = Mock(return_value=1)
    manager.start_replay_mode = AsyncMock(return_value=True)
    manager.finish_replay_mode = AsyncMock(return_value=2)
    manager.send_to_connection = AsyncMock(return_value=True)
    manager.disconnect = AsyncMock()

    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=[json.dumps({"type": "ping"}), WebSocketDisconnect()])

    class SessionService:
        def __init__(self, db):
            self.db = db

        async def get_session(self, session_id: str):
            return SimpleNamespace(id=session_id)

        @staticmethod
        def _session_to_event_data(session):
            return {"session_id": session.id}

    @asynccontextmanager
    async def fake_scope():
        yield AsyncMock()

    replay_pending = AsyncMock()
    replay_events = AsyncMock(return_value=3)
    monkeypatch.setattr(router_module, "get_connection_manager", lambda: manager)
    monkeypatch.setattr(
        router_module,
        "_authenticate_websocket",
        AsyncMock(return_value=SimpleUser("auth-user")),
    )
    monkeypatch.setattr(router_module, "async_session_scope", fake_scope)
    monkeypatch.setattr("app.modules.agent_session.services.agent_session_service.AgentSessionService", SessionService)
    monkeypatch.setattr(router_module, "_replay_pending_tool_decision", replay_pending)
    monkeypatch.setattr(router_module, "_replay_session_events", replay_events)

    await router_module.websocket_session_endpoint(websocket, "session-1", user_id="user-1", last_seq=0)

    manager.connect.assert_awaited_once_with(
        websocket,
        user_id="auth-user",
        session_id="session-1",
    )
    manager.start_replay_mode.assert_awaited_once_with("conn-1")
    replay_pending.assert_awaited_once_with(manager, "conn-1", "session-1")
    replay_events.assert_awaited_once_with(
        manager=manager,
        connection_id="conn-1",
        session_id="session-1",
        last_seq=0,
    )
    manager.finish_replay_mode.assert_awaited_once_with("conn-1")
    manager.disconnect.assert_awaited_once_with("conn-1")


@pytest.mark.asyncio
async def test_websocket_session_endpoint_handles_json_error_and_missing_session(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = Mock()
    manager.connect = AsyncMock(return_value="conn-2")
    manager.get_connection_count = Mock(return_value=1)
    manager.send_to_connection = AsyncMock(return_value=True)
    manager.disconnect = AsyncMock()

    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=["{bad json", WebSocketDisconnect()])
    websocket.send_json = AsyncMock()

    class SessionService:
        def __init__(self, db):
            self.db = db

        async def get_session(self, session_id: str):
            return None

    @asynccontextmanager
    async def fake_scope():
        yield AsyncMock()

    monkeypatch.setattr(router_module, "get_connection_manager", lambda: manager)
    monkeypatch.setattr(
        router_module,
        "_authenticate_websocket",
        AsyncMock(return_value=SimpleUser("auth-user")),
    )
    monkeypatch.setattr(router_module, "async_session_scope", fake_scope)
    monkeypatch.setattr("app.modules.agent_session.services.agent_session_service.AgentSessionService", SessionService)
    monkeypatch.setattr(router_module, "_replay_pending_tool_decision", AsyncMock())
    monkeypatch.setattr(router_module, "_replay_session_events", AsyncMock())

    await router_module.websocket_session_endpoint(websocket, "session-2", user_id=None, last_seq=None)

    websocket.send_json.assert_awaited_once_with({"type": "error", "message": "Invalid JSON"})
    manager.disconnect.assert_awaited_once_with("conn-2")


@pytest.mark.asyncio
async def test_websocket_global_endpoint_invalid_json_and_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = Mock()
    manager.connect = AsyncMock(return_value="conn-global")
    manager.disconnect = AsyncMock()

    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=["not-json", RuntimeError("boom")])
    websocket.send_json = AsyncMock()

    monkeypatch.setattr(router_module, "get_connection_manager", lambda: manager)
    monkeypatch.setattr(
        router_module,
        "_authenticate_websocket",
        AsyncMock(return_value=SimpleUser("auth-user")),
    )
    handle_message = AsyncMock()
    monkeypatch.setattr(router_module, "_handle_client_message", handle_message)

    await router_module.websocket_global_endpoint(websocket, user_id="user-1")

    manager.connect.assert_awaited_once_with(websocket, user_id="auth-user")
    websocket.send_json.assert_awaited_once_with({"type": "error", "message": "Invalid JSON"})
    manager.disconnect.assert_awaited_once_with("conn-global")


@pytest.mark.asyncio
async def test_replay_pending_tool_decision_noop_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = AsyncMock()

    @asynccontextmanager
    async def fake_scope():
        yield AsyncMock()

    monkeypatch.setattr(router_module, "async_session_scope", fake_scope)

    class MissingTaskRepo:
        def __init__(self, db):
            self.db = db

        async def find_active_by_session(self, session_id: str):
            return None

    monkeypatch.setattr("app.modules.agent_session.repositories.task_repository.TaskRepository", MissingTaskRepo)
    await router_module._replay_pending_tool_decision(manager, "conn-1", "session-1")
    manager.send_to_connection.assert_not_called()

    class InvalidTaskRepo(MissingTaskRepo):
        async def find_active_by_session(self, session_id: str):
            return SimpleNamespace(task_id="task-1", status="awaiting_permission", data="{broken")

    monkeypatch.setattr("app.modules.agent_session.repositories.task_repository.TaskRepository", InvalidTaskRepo)
    await router_module._replay_pending_tool_decision(manager, "conn-1", "session-1")
    manager.send_to_connection.assert_not_called()


def test_extract_websocket_token_prefers_authorization_header() -> None:
    websocket = SimpleNamespace(
        headers={"authorization": "Bearer header.jwt.token", "x-internal-token": "internal-secret"},
        query_params={"token": "query.jwt.token", "internal_token": "query-internal"},
    )

    assert router_module._extract_websocket_token(websocket) == "header.jwt.token"


@pytest.mark.asyncio
async def test_authenticate_websocket_rejects_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = SimpleNamespace(
        headers={},
        query_params={},
        close=AsyncMock(),
    )

    user = await router_module._authenticate_websocket(websocket)

    assert user is None
    websocket.close.assert_awaited_once_with(code=4401, reason="Missing authentication token")


@pytest.mark.asyncio
async def test_authenticate_websocket_accepts_internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = SimpleNamespace(
        headers={},
        query_params={"token": "internal-secret"},
        close=AsyncMock(),
    )
    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(INTERNAL_API_TOKEN="internal-secret"),
    )

    user = await router_module._authenticate_websocket(websocket)

    assert user is not None
    assert user.id == "internal-test-user"
    websocket.close.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_websocket_validates_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = SimpleNamespace(
        headers={},
        query_params={"token": "aaa.bbb.ccc"},
        close=AsyncMock(),
    )
    auth_service = AsyncMock()
    auth_service.validate_access_token.return_value = SimpleUser("user-123")
    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(INTERNAL_API_TOKEN="internal-secret"),
    )
    monkeypatch.setattr(router_module, "get_auth_service", lambda: auth_service)

    user = await router_module._authenticate_websocket(websocket)

    assert user is not None
    assert user.id == "user-123"
    auth_service.validate_access_token.assert_awaited_once_with("aaa.bbb.ccc")
    websocket.close.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_websocket_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = SimpleNamespace(
        headers={},
        query_params={"token": "aaa.bbb.ccc"},
        close=AsyncMock(),
    )
    auth_service = AsyncMock()
    auth_service.validate_access_token.return_value = None
    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(INTERNAL_API_TOKEN="internal-secret"),
    )
    monkeypatch.setattr(router_module, "get_auth_service", lambda: auth_service)

    user = await router_module._authenticate_websocket(websocket)

    assert user is None
    websocket.close.assert_awaited_once_with(
        code=4401,
        reason="Invalid or expired authentication token",
    )
