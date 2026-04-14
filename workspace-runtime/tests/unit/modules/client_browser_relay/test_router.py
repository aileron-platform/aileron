from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

router_module = importlib.import_module("app.modules.client_browser_relay.router")


def create_client(monkeypatch, service) -> TestClient:
    monkeypatch.setattr(router_module, "get_settings", lambda: SimpleNamespace(PORT=3002))
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)

    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/v1")
    return TestClient(app)


def test_get_relay_status_uses_request_host(monkeypatch) -> None:
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

    response = client.get("/api/v1/client-browser-relay/", headers={"host": "relay.example:4010"})

    assert response.status_code == 200
    assert response.json() == {
        "wsEndpoint": "ws://relay.example:4010/api/v1/client-browser-relay/cdp",
        "extensionConnected": True,
        "mode": "extension",
        "connectedTargetsCount": 3,
        "playwrightClientsCount": 2,
    }


def test_list_named_pages_returns_service_result(monkeypatch) -> None:
    service = SimpleNamespace(get_named_pages=lambda: ["page-a", "page-b"])
    client = create_client(monkeypatch, service)

    response = client.get("/api/v1/client-browser-relay/pages")

    assert response.status_code == 200
    assert response.json() == {"pages": ["page-a", "page-b"]}


def test_get_or_create_page_requires_extension_connection(monkeypatch) -> None:
    service = SimpleNamespace(extension_ws=None)
    client = create_client(monkeypatch, service)

    response = client.post("/api/v1/client-browser-relay/pages", json={"name": "demo"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Extension not connected"


def test_get_or_create_page_returns_created_page(monkeypatch) -> None:
    service = SimpleNamespace(
        extension_ws=object(),
        get_or_create_named_page=AsyncMock(
            return_value={
                "wsEndpoint": "ws://localhost:3002/api/v1/client-browser-relay/cdp",
                "name": "demo",
                "targetId": "target-1",
                "url": "about:blank",
            }
        ),
    )
    client = create_client(monkeypatch, service)

    response = client.post("/api/v1/client-browser-relay/pages", json={"name": "demo"})

    assert response.status_code == 200
    assert response.json()["targetId"] == "target-1"
    service.get_or_create_named_page.assert_awaited_once_with("demo", "testserver", 3002)


def test_get_or_create_page_handles_empty_name_and_service_error(monkeypatch) -> None:
    service = SimpleNamespace(
        extension_ws=object(),
        get_or_create_named_page=AsyncMock(side_effect=RuntimeError("boom")),
    )
    client = create_client(monkeypatch, service)

    bad_name = client.post("/api/v1/client-browser-relay/pages", json={"name": ""})
    failed = client.post("/api/v1/client-browser-relay/pages", json={"name": "demo"})

    assert bad_name.status_code == 400
    assert failed.status_code == 500
    assert failed.json()["detail"] == "boom"


def test_get_relay_status_handles_invalid_host_port(monkeypatch) -> None:
    service = SimpleNamespace(
        get_status=lambda host, port: {
            "wsEndpoint": f"ws://{host}:{port}/api/v1/client-browser-relay/cdp",
            "extensionConnected": False,
            "mode": "extension",
            "connectedTargetsCount": 0,
            "playwrightClientsCount": 0,
        }
    )
    client = create_client(monkeypatch, service)

    response = client.get("/api/v1/client-browser-relay/", headers={"host": "relay.example:not-a-port"})

    assert response.status_code == 200
    assert response.json()["wsEndpoint"] == "ws://relay.example:3002/api/v1/client-browser-relay/cdp"


def test_delete_named_page_returns_success(monkeypatch) -> None:
    service = SimpleNamespace(delete_named_page=AsyncMock(return_value=True))
    client = create_client(monkeypatch, service)

    response = client.delete("/api/v1/client-browser-relay/pages/demo")

    assert response.status_code == 200
    assert response.json() == {"success": True}


class FakeWebSocket:
    def __init__(self, messages=None, disconnect_immediately: bool = False):
        self.messages = list(messages or [])
        self.accept = AsyncMock()
        self.close = AsyncMock()
        self.send_json = AsyncMock()
        self.disconnect_immediately = disconnect_immediately

    async def receive_text(self):
        from fastapi import WebSocketDisconnect

        if self.disconnect_immediately or not self.messages:
            raise WebSocketDisconnect()
        item = self.messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _client_browser_ws_disconnect():
    from fastapi import WebSocketDisconnect

    raise WebSocketDisconnect()


def test_handle_cdp_connection_rejects_duplicate_client(monkeypatch) -> None:
    service = SimpleNamespace(
        register_playwright_client=AsyncMock(return_value=False),
        unregister_playwright_client=AsyncMock(),
    )
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)
    websocket = FakeWebSocket()

    import asyncio

    asyncio.run(router_module._handle_cdp_connection(websocket, "client-1"))

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=1000, reason="Client ID already connected")
    service.unregister_playwright_client.assert_not_awaited()


def test_handle_cdp_connection_routes_commands_and_errors(monkeypatch) -> None:
    target = SimpleNamespace(
        target_id="target-1",
        target_info=SimpleNamespace(target_id="target-1", type="page", title="Demo", url="about:blank"),
    )
    service = SimpleNamespace(
        extension_ws=object(),
        connected_targets={"target-1": target},
        register_playwright_client=AsyncMock(return_value=True),
        unregister_playwright_client=AsyncMock(),
        route_cdp_command=AsyncMock(side_effect=[{}, {}, {"sessionId": "session-1"}, RuntimeError("boom")]),
        send_attached_to_target=AsyncMock(),
        send_to_playwright=AsyncMock(),
    )
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)
    websocket = FakeWebSocket(
        messages=[
            json.dumps({"id": 1, "method": "Target.setAutoAttach", "params": {}}),
            json.dumps({"id": 2, "method": "Target.setDiscoverTargets", "params": {"discover": True}}),
            json.dumps({"id": 3, "method": "Target.attachToTarget", "params": {"targetId": "target-1"}}),
            "not-json",
            json.dumps({"id": 4, "method": "Broken.method", "params": {}}),
        ],
        disconnect_immediately=False,
    )

    import asyncio

    asyncio.run(router_module._handle_cdp_connection(websocket, "client-2"))

    assert service.register_playwright_client.await_count == 1
    assert service.send_attached_to_target.await_count == 2
    sent_payloads = [call.args[0] for call in service.send_to_playwright.await_args_list]
    assert any(payload.get("method") == "Target.targetCreated" for payload in sent_payloads)
    assert any(payload.get("error", {}).get("message") == "boom" for payload in sent_payloads)
    service.unregister_playwright_client.assert_awaited_once_with("client-2")


def test_handle_cdp_connection_extension_not_connected(monkeypatch) -> None:
    service = SimpleNamespace(
        extension_ws=None,
        register_playwright_client=AsyncMock(return_value=True),
        unregister_playwright_client=AsyncMock(),
        send_to_playwright=AsyncMock(),
    )
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)
    websocket = FakeWebSocket(messages=[json.dumps({"id": 1, "method": "Page.enable"})])

    import asyncio

    asyncio.run(router_module._handle_cdp_connection(websocket, "client-3"))

    payload = service.send_to_playwright.await_args.args[0]
    assert payload["error"]["message"] == "Extension not connected"


def test_extension_endpoint_handles_messages_and_cleanup(monkeypatch) -> None:
    service = SimpleNamespace(
        register_extension=AsyncMock(),
        unregister_extension=AsyncMock(),
        extension_ws=None,
        handle_extension_response=Mock(),
        handle_target_attached=AsyncMock(),
        handle_target_detached=AsyncMock(),
        handle_target_info_changed=AsyncMock(),
        send_to_playwright=AsyncMock(),
    )
    websocket = FakeWebSocket(
        messages=[
            json.dumps({"id": 1, "result": {"ok": True}}),
            json.dumps({"method": "log", "params": {"level": "info", "args": ["hello"]}}),
            json.dumps(
                {
                    "method": "forwardCDPEvent",
                    "params": {"method": "Target.attachedToTarget", "params": {"sessionId": "s1", "targetInfo": {}}},
                }
            ),
            json.dumps(
                {
                    "method": "forwardCDPEvent",
                    "params": {"method": "Target.detachedFromTarget", "params": {"sessionId": "s2"}},
                }
            ),
            json.dumps(
                {
                    "method": "forwardCDPEvent",
                    "params": {"method": "Target.targetInfoChanged", "params": {"targetInfo": {"targetId": "t1"}}},
                }
            ),
            json.dumps(
                {
                    "method": "forwardCDPEvent",
                    "params": {"method": "Network.requestWillBeSent", "params": {"url": "x"}, "sessionId": "s3"},
                }
            ),
        ],
    )
    service.extension_ws = websocket
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)

    import asyncio

    asyncio.run(router_module.extension_endpoint(websocket))

    service.register_extension.assert_awaited_once_with(websocket)
    service.handle_extension_response.assert_called_once_with(1, {"ok": True}, None)
    service.handle_target_attached.assert_awaited_once()
    service.handle_target_detached.assert_awaited_once_with("s2")
    service.handle_target_info_changed.assert_awaited_once()
    service.send_to_playwright.assert_awaited_once()
    service.unregister_extension.assert_awaited_once()


def test_extension_endpoint_invalid_json_closes_socket(monkeypatch) -> None:
    service = SimpleNamespace(
        register_extension=AsyncMock(),
        unregister_extension=AsyncMock(),
        extension_ws=None,
    )
    websocket = FakeWebSocket(messages=["{bad"])
    service.extension_ws = websocket
    monkeypatch.setattr(router_module, "get_relay_service", lambda: service)

    import asyncio

    asyncio.run(router_module.extension_endpoint(websocket))

    websocket.close.assert_awaited_once_with(code=1000, reason="Invalid JSON")
