from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

router_module = importlib.import_module("app.modules.client_browser_relay.router")


def create_client(monkeypatch, service) -> TestClient:
    monkeypatch.setattr(
        router_module, "get_settings", lambda: SimpleNamespace(PORT=3002)
    )
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)
    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/v1")
    return TestClient(app)


def test_public_health_returns_only_minimal_status(monkeypatch) -> None:
    client = create_client(monkeypatch, SimpleNamespace())

    response = client.get("/api/v1/client-browser-relay/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_authenticated_status_uses_request_host(monkeypatch) -> None:
    service = SimpleNamespace(
        get_status=lambda host, port: {
            "wsEndpoint": f"ws://{host}:{port}/api/v1/client-browser-relay/cdp",
            "extensionConnected": True,
            "mode": "extension",
            "connectedTargetsCount": 3,
            "playwrightClientsCount": 2,
        }
    )
    client = create_client(monkeypatch, service)

    response = client.get(
        "/api/v1/client-browser-relay",
        headers={"host": "relay.example:4010"},
    )

    assert response.status_code == 200
    assert response.json()["wsEndpoint"] == (
        "ws://relay.example:4010/api/v1/client-browser-relay/cdp"
    )
    assert response.json()["extensionConnected"] is True


def test_page_routes_return_code_only_failures(monkeypatch) -> None:
    client = create_client(monkeypatch, SimpleNamespace(extension_ws=None))

    response = client.post("/api/v1/client-browser-relay/pages", json={"name": "demo"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": {"errorCode": "BROWSER_EXTENSION_NOT_CONNECTED"}
    }


def test_page_routes_use_relay_service(monkeypatch) -> None:
    service = SimpleNamespace(
        extension_ws=object(),
        get_named_pages=lambda: ["page-a", "page-b"],
        get_or_create_named_page=AsyncMock(
            return_value={
                "wsEndpoint": "ws://localhost:3002/api/v1/client-browser-relay/cdp",
                "name": "demo",
                "targetId": "target-1",
                "url": "about:blank",
            }
        ),
        delete_named_page=AsyncMock(return_value=True),
    )
    client = create_client(monkeypatch, service)

    listed = client.get("/api/v1/client-browser-relay/pages")
    created = client.post("/api/v1/client-browser-relay/pages", json={"name": "demo"})
    deleted = client.delete("/api/v1/client-browser-relay/pages/demo")

    assert listed.json() == {"pages": ["page-a", "page-b"]}
    assert created.json()["targetId"] == "target-1"
    assert deleted.json() == {"success": True}


class FakeWebSocket:
    def __init__(
        self,
        *,
        messages=None,
        headers=None,
        query_params=None,
    ) -> None:
        self.messages = list(messages or [])
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.accept = AsyncMock()
        self.close = AsyncMock()

    async def receive_text(self) -> str:
        if not self.messages:
            raise WebSocketDisconnect()
        value = self.messages.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


async def _allow_websocket(_websocket) -> tuple[bool, str | None]:
    return True, None


def test_cdp_connection_checks_user_gate_before_accept(monkeypatch) -> None:
    service = SimpleNamespace(
        register_playwright_client=AsyncMock(return_value=False),
        unregister_playwright_client=AsyncMock(),
    )
    monkeypatch.setattr(router_module, "_authorize_user_websocket", _allow_websocket)
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)
    websocket = FakeWebSocket()

    import asyncio

    asyncio.run(router_module._handle_cdp_connection(websocket, "client-1"))

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(
        code=4409, reason="BROWSER_CLIENT_ID_CONFLICT"
    )


def test_cdp_connection_routes_command_failures_as_codes(monkeypatch) -> None:
    service = SimpleNamespace(
        extension_ws=object(),
        connected_targets={},
        register_playwright_client=AsyncMock(return_value=True),
        unregister_playwright_client=AsyncMock(),
        route_cdp_command=AsyncMock(side_effect=RuntimeError("sensitive detail")),
        send_to_playwright=AsyncMock(),
    )
    monkeypatch.setattr(router_module, "_authorize_user_websocket", _allow_websocket)
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)
    websocket = FakeWebSocket(
        messages=[json.dumps({"id": 1, "method": "Broken.method"})]
    )

    import asyncio

    asyncio.run(router_module._handle_cdp_connection(websocket, "client-1"))

    sent = service.send_to_playwright.await_args.args[0]
    assert sent["error"] == {"code": "BROWSER_CDP_COMMAND_FAILED"}
    assert "sensitive detail" not in str(sent)


def test_extension_rejects_every_query_string(monkeypatch) -> None:
    verifier = Mock()
    monkeypatch.setattr(
        router_module, "get_manager_assertion_verifier", lambda: verifier
    )
    websocket = FakeWebSocket(query_params={"pairing": "secret"})

    import asyncio

    asyncio.run(router_module.extension_endpoint(websocket))

    websocket.close.assert_awaited_once_with(
        code=4401, reason="BROWSER_PAIRING_QUERY_REJECTED"
    )
    verifier.verify_browser_pairing.assert_not_called()


def test_extension_requires_pairing_protocol_and_consumes_assertion(
    monkeypatch,
) -> None:
    verifier = Mock()
    pairing = SimpleNamespace(
        pairing_session_id="pairing-session-one",
        jti="pairing-jti-one",
        browser_workload_identity="browser-workload-one",
    )
    verifier.verify_browser_pairing.return_value = pairing
    service = SimpleNamespace(
        extension_ws=None,
        register_extension=AsyncMock(),
        unregister_extension=AsyncMock(),
    )
    monkeypatch.setattr(
        router_module, "get_manager_assertion_verifier", lambda: verifier
    )
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)
    websocket = FakeWebSocket(
        headers={
            "sec-websocket-protocol": (
                "aileron-browser-extension, assertion.header.payload.signature"
            )
        }
    )

    import asyncio

    asyncio.run(router_module.extension_endpoint(websocket))

    verifier.verify_browser_pairing.assert_called_once_with("header.payload.signature")
    websocket.accept.assert_awaited_once_with(subprotocol="aileron-browser-extension")
    service.register_extension.assert_awaited_once_with(websocket, pairing)
    service.unregister_extension.assert_not_awaited()
