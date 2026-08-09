from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.websockets import WebSocketDisconnect

from app.modules.auth.execution_grant import ExecutionGrantInvalid

websocket_module = importlib.import_module("app.modules.thread.websocket.router")


class FakeWebSocket:
    def __init__(self, *, headers=None, query_params=None) -> None:
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.close = AsyncMock()

    async def receive_text(self) -> str:
        raise WebSocketDisconnect()


def configure(monkeypatch, *, verifier: Mock | None = None) -> Mock:
    resolved = verifier or Mock()
    resolved.verify.return_value = SimpleNamespace(subject="user-a")
    monkeypatch.setattr(
        websocket_module,
        "get_settings",
        lambda: SimpleNamespace(
            AILERON_WORKSPACE_ID="workspace-a",
            effective_allowed_origins=["https://app.example.test"],
        ),
    )
    monkeypatch.setattr(
        websocket_module, "get_execution_grant_verifier", lambda: resolved
    )
    return resolved


@pytest.mark.asyncio
async def test_thread_websocket_verifies_agent_grant_before_connect(monkeypatch) -> None:
    verifier = configure(monkeypatch)
    manager = SimpleNamespace(
        connect=AsyncMock(return_value="connection-a"),
        disconnect=AsyncMock(),
    )
    monkeypatch.setattr(
        websocket_module, "get_thread_connection_manager", lambda: manager
    )
    websocket = FakeWebSocket(
        headers={
            "origin": "https://app.example.test",
            "sec-websocket-protocol": "aileron-thread-v1, bearer.c2lnbmVkLWdyYW50",
        }
    )

    await websocket_module.websocket_thread_events_endpoint(websocket)

    verifier.verify.assert_called_once_with("signed-grant", action="agent")
    manager.connect.assert_awaited_once_with(
        websocket,
        workspace_id="workspace-a",
        user_id="user-a",
        subprotocol="aileron-thread-v1",
    )
    manager.disconnect.assert_awaited_once_with("connection-a")


@pytest.mark.asyncio
async def test_thread_websocket_rejects_query_token(monkeypatch) -> None:
    verifier = configure(monkeypatch)
    websocket = FakeWebSocket(
        headers={"origin": "https://app.example.test"},
        query_params={"token": "signed-grant"},
    )

    assert await websocket_module._authenticate_websocket(websocket) is None
    websocket.close.assert_awaited_once_with(
        code=4401, reason="THREAD_AUTH_TOKEN_QUERY_REJECTED"
    )
    verifier.verify.assert_not_called()


@pytest.mark.asyncio
async def test_thread_websocket_rejects_authorization_header(monkeypatch) -> None:
    verifier = configure(monkeypatch)
    websocket = FakeWebSocket(
        headers={
            "origin": "https://app.example.test",
            "authorization": "Bearer signed-grant",
        }
    )

    assert await websocket_module._authenticate_websocket(websocket) is None
    websocket.close.assert_awaited_once_with(
        code=4401, reason="THREAD_AUTH_HEADER_REJECTED"
    )
    verifier.verify.assert_not_called()


@pytest.mark.asyncio
async def test_thread_websocket_rejects_non_exact_origin(monkeypatch) -> None:
    verifier = configure(monkeypatch)
    websocket = FakeWebSocket(
        headers={
            "origin": "https://evil.example.test",
            "sec-websocket-protocol": "aileron-thread-v1, bearer.c2lnbmVkLWdyYW50",
        }
    )

    assert await websocket_module._authenticate_websocket(websocket) is None
    websocket.close.assert_awaited_once_with(code=4403, reason="THREAD_ORIGIN_INVALID")
    verifier.verify.assert_not_called()


@pytest.mark.asyncio
async def test_thread_websocket_rejects_invalid_grant(monkeypatch) -> None:
    verifier = configure(monkeypatch)
    verifier.verify.side_effect = ExecutionGrantInvalid(
        "WORKSPACE_EXECUTION_GRANT_EXPIRED"
    )
    websocket = FakeWebSocket(
        headers={
            "origin": "https://app.example.test",
            "sec-websocket-protocol": "aileron-thread-v1, bearer.c2lnbmVkLWdyYW50",
        }
    )

    assert await websocket_module._authenticate_websocket(websocket) is None
    websocket.close.assert_awaited_once_with(
        code=4401, reason="WORKSPACE_EXECUTION_GRANT_EXPIRED"
    )
