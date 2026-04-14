from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.modules.client_browser_relay.models import ConnectedTarget, TargetInfo
from app.modules.client_browser_relay.service import RelayService


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent_texts: list[str] = []
        self.close_calls: list[tuple[int | None, str | None]] = []

    async def send_text(self, text: str) -> None:
        self.sent_texts.append(text)

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        self.close_calls.append((code, reason))


class FailingWebSocket(FakeWebSocket):
    async def send_text(self, text: str) -> None:
        raise RuntimeError("send failed")

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        raise RuntimeError("close failed")


@pytest.fixture
def relay_service() -> RelayService:
    return RelayService()


@pytest.mark.asyncio
async def test_register_playwright_client_rejects_duplicate_ids(relay_service: RelayService) -> None:
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()

    assert await relay_service.register_playwright_client("client-1", ws1) is True
    assert await relay_service.register_playwright_client("client-1", ws2) is False


@pytest.mark.asyncio
async def test_send_to_playwright_broadcasts_to_all_clients(relay_service: RelayService) -> None:
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()
    await relay_service.register_playwright_client("client-1", ws1)
    await relay_service.register_playwright_client("client-2", ws2)

    await relay_service.send_to_playwright({"method": "ping"})

    assert json.loads(ws1.sent_texts[0]) == {"method": "ping"}
    assert json.loads(ws2.sent_texts[0]) == {"method": "ping"}


@pytest.mark.asyncio
async def test_send_to_playwright_handles_targeted_and_broadcast_errors(relay_service: RelayService) -> None:
    ok_ws = FakeWebSocket()
    failing_ws = FailingWebSocket()
    await relay_service.register_playwright_client("client-1", ok_ws)
    await relay_service.register_playwright_client("client-2", failing_ws)

    await relay_service.send_to_playwright({"method": "one"}, client_id="client-2")
    await relay_service.send_to_playwright({"method": "two"})

    assert json.loads(ok_ws.sent_texts[0]) == {"method": "two"}


@pytest.mark.asyncio
async def test_send_to_extension_waits_for_response(relay_service: RelayService) -> None:
    ws = FakeWebSocket()
    relay_service.extension_ws = ws

    async def respond() -> None:
        await asyncio.sleep(0)
        relay_service.handle_extension_response(1, {"ok": True}, None)

    task = asyncio.create_task(relay_service.send_to_extension("forwardCDPCommand"))
    await respond()
    result = await task

    assert result == {"ok": True}
    assert json.loads(ws.sent_texts[0])["method"] == "forwardCDPCommand"


@pytest.mark.asyncio
async def test_route_cdp_command_handles_local_targets(relay_service: RelayService) -> None:
    target = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(
            targetId="target-1",
            type="page",
            title="Demo",
            url="about:blank",
            browserContextId="ctx-1",
        ),
    )
    relay_service.connected_targets[target.session_id] = target

    attach_result = await relay_service.route_cdp_command(
        "Target.attachToTarget",
        {"targetId": "target-1"},
    )
    targets_result = await relay_service.route_cdp_command("Target.getTargets")
    info_result = await relay_service.route_cdp_command(
        "Target.getTargetInfo",
        {"targetId": "target-1"},
    )

    assert attach_result == {"sessionId": "session-1"}
    assert targets_result["targetInfos"][0]["targetId"] == "target-1"
    assert info_result["targetInfo"]["browserContextId"] == "ctx-1"


@pytest.mark.asyncio
async def test_send_attached_to_target_deduplicates_known_targets(relay_service: RelayService) -> None:
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()
    await relay_service.register_playwright_client("client-1", ws1)
    await relay_service.register_playwright_client("client-2", ws2)
    relay_service.playwright_clients["client-1"].known_targets.add("target-1")

    target = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(targetId="target-1", title="Demo"),
    )

    await relay_service.send_attached_to_target(target)
    await relay_service.send_attached_to_target(target, client_id="client-1")

    assert len(ws1.sent_texts) == 0
    assert len(ws2.sent_texts) == 1
    assert json.loads(ws2.sent_texts[0])["method"] == "Target.attachedToTarget"


@pytest.mark.asyncio
async def test_handle_target_attached_resolves_waiting_future(relay_service: RelayService) -> None:
    future = asyncio.get_running_loop().create_future()
    relay_service._target_attachment_futures["target-1"] = future

    await relay_service.handle_target_attached(
        "session-1",
        {
            "targetId": "target-1",
            "type": "page",
            "title": "Demo",
            "url": "about:blank",
            "browserContextId": "ctx-1",
        },
    )

    assert future.done() is True
    assert future.result() == "session-1"
    assert relay_service.connected_targets["session-1"].target_info.url == "about:blank"


@pytest.mark.asyncio
async def test_get_or_create_named_page_returns_existing_mapping(relay_service: RelayService) -> None:
    target = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(targetId="target-1", url="https://example.com"),
    )
    relay_service.connected_targets[target.session_id] = target
    relay_service.named_pages["demo"] = target.session_id

    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_send_to_extension(method: str, params: dict[str, object], timeout: float = 30.0):
        calls.append((method, params))
        return {}

    relay_service.send_to_extension = fake_send_to_extension  # type: ignore[method-assign]

    result = await relay_service.get_or_create_named_page("demo", "localhost", 3002)

    assert result == {
        "wsEndpoint": "ws://localhost:3002/api/v1/client-browser-relay/cdp",
        "name": "demo",
        "targetId": "target-1",
        "url": "https://example.com",
    }
    assert calls == [
        (
            "forwardCDPCommand",
            {"method": "Target.activateTarget", "params": {"targetId": "target-1"}},
        )
    ]


@pytest.mark.asyncio
async def test_unregister_extension_closes_all_playwright_clients(relay_service: RelayService) -> None:
    relay_service.extension_ws = FakeWebSocket()
    relay_service.playwright_clients["client-1"] = object()  # type: ignore[assignment]
    relay_service.playwright_websockets["client-1"] = FakeWebSocket()  # type: ignore[assignment]
    relay_service.named_pages["demo"] = "session-1"
    relay_service.connected_targets["session-1"] = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(targetId="target-1"),
    )

    await relay_service.unregister_extension()

    assert relay_service.extension_ws is None
    assert relay_service.playwright_clients == {}
    assert relay_service.playwright_websockets == {}
    assert relay_service.named_pages == {}
    assert relay_service.connected_targets == {}


@pytest.mark.asyncio
async def test_unregister_playwright_client_and_extension_tolerate_failures(relay_service: RelayService) -> None:
    pending = asyncio.get_running_loop().create_future()
    relay_service.extension_pending_requests[1] = pending
    relay_service.extension_ws = FakeWebSocket()  # type: ignore[assignment]
    relay_service.playwright_clients["client-1"] = object()  # type: ignore[assignment]
    relay_service.playwright_websockets["client-1"] = FailingWebSocket()  # type: ignore[assignment]

    await relay_service.unregister_playwright_client("client-1")
    assert "client-1" not in relay_service.playwright_clients

    relay_service.playwright_clients["client-1"] = object()  # type: ignore[assignment]
    relay_service.playwright_websockets["client-1"] = FailingWebSocket()  # type: ignore[assignment]
    await relay_service.unregister_extension()

    assert pending.done() is True
    assert relay_service.extension_pending_requests == {}


def test_get_status_reports_counts(relay_service: RelayService) -> None:
    relay_service.extension_ws = FakeWebSocket()  # type: ignore[assignment]
    relay_service.playwright_clients["client-1"] = object()  # type: ignore[assignment]
    relay_service.connected_targets["session-1"] = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(targetId="target-1"),
    )

    status = relay_service.get_status("localhost", 3002)

    assert status == {
        "wsEndpoint": "ws://localhost:3002/api/v1/client-browser-relay/cdp",
        "extensionConnected": True,
        "mode": "extension",
        "connectedTargetsCount": 1,
        "playwrightClientsCount": 1,
    }


@pytest.mark.asyncio
async def test_register_extension_replaces_existing_and_rejects_pending(relay_service: RelayService) -> None:
    old_ws = FakeWebSocket()
    new_ws = FakeWebSocket()
    future = asyncio.get_running_loop().create_future()
    relay_service.extension_ws = old_ws
    relay_service.connected_targets["s1"] = ConnectedTarget(
        session_id="s1",
        target_id="t1",
        target_info=TargetInfo(targetId="t1"),
    )
    relay_service.named_pages["demo"] = "s1"
    relay_service.extension_pending_requests[1] = future

    await relay_service.register_extension(new_ws)

    assert old_ws.close_calls == [(4001, "Extension Replaced")]
    assert relay_service.extension_ws is new_ws
    assert relay_service.connected_targets == {}
    assert relay_service.named_pages == {}
    assert future.done() is True


@pytest.mark.asyncio
async def test_register_extension_tolerates_close_failure(relay_service: RelayService) -> None:
    relay_service.extension_ws = FailingWebSocket()  # type: ignore[assignment]

    await relay_service.register_extension(FakeWebSocket())  # type: ignore[arg-type]

    assert relay_service.extension_ws is not None


@pytest.mark.asyncio
async def test_send_to_extension_timeout_and_error_response(relay_service: RelayService) -> None:
    relay_service.extension_ws = FakeWebSocket()  # type: ignore[assignment]

    with pytest.raises(Exception, match="timeout"):
        await relay_service.send_to_extension("forwardCDPCommand", timeout=0.01)

    future = asyncio.get_running_loop().create_future()
    relay_service.extension_pending_requests[2] = future
    relay_service.handle_extension_response(2, None, "boom")
    with pytest.raises(Exception, match="boom"):
        await future

    relay_service.handle_extension_response(999, None, None)


@pytest.mark.asyncio
async def test_send_to_extension_requires_extension_connection(relay_service: RelayService) -> None:
    with pytest.raises(Exception, match="Extension not connected"):
        await relay_service.send_to_extension("forwardCDPCommand")


@pytest.mark.asyncio
async def test_route_cdp_command_additional_local_paths(relay_service: RelayService) -> None:
    relay_service.send_to_extension = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]
    target = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(
            targetId="target-1",
            type="page",
            title="Demo",
            url="about:blank",
            browserContextId="ctx-1",
        ),
    )
    relay_service.connected_targets[target.session_id] = target

    assert await relay_service.route_cdp_command("Browser.setDownloadBehavior") == {}
    assert await relay_service.route_cdp_command("Target.setAutoAttach") == {}
    assert await relay_service.route_cdp_command("Target.setDiscoverTargets") == {}
    assert await relay_service.route_cdp_command("Target.attachToBrowserTarget") == {"sessionId": "browser"}
    assert await relay_service.route_cdp_command("Target.detachFromTarget", {"sessionId": "browser"}) == {}
    assert (await relay_service.route_cdp_command("Target.getTargetInfo", session_id="session-1"))["targetInfo"]["targetId"] == "target-1"
    assert (await relay_service.route_cdp_command("Target.createTarget", {"url": "about:blank"})) == {"ok": True}
    assert (await relay_service.route_cdp_command("Runtime.evaluate", {"expression": "1+1"}, "session-1")) == {"ok": True}

    with pytest.raises(Exception, match="targetId is required"):
        await relay_service.route_cdp_command("Target.attachToTarget", {})

    with pytest.raises(Exception, match="not found"):
        await relay_service.route_cdp_command("Target.attachToTarget", {"targetId": "missing"})


@pytest.mark.asyncio
async def test_route_cdp_command_supports_fallback_paths(relay_service: RelayService) -> None:
    relay_service.send_to_extension = AsyncMock(return_value={"forwarded": True})  # type: ignore[method-assign]
    relay_service.connected_targets["session-1"] = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(targetId="target-1", title="Demo", url="https://example.com"),
    )

    result = await relay_service.route_cdp_command("Target.getTargetInfo")
    detached = await relay_service.route_cdp_command("Target.detachFromTarget", {"sessionId": "session-1"})
    auto_attach = await relay_service.route_cdp_command("Target.setAutoAttach", session_id="session-1")

    assert result["targetInfo"]["targetId"] == "target-1"
    assert detached == {"forwarded": True}
    assert auto_attach == {"forwarded": True}


@pytest.mark.asyncio
async def test_target_detach_info_change_delete_named_page_and_create_timeout(relay_service: RelayService) -> None:
    relay_service.send_to_playwright = AsyncMock()  # type: ignore[method-assign]
    relay_service.send_attached_to_target = AsyncMock()  # type: ignore[method-assign]
    relay_service.send_to_extension = AsyncMock(return_value={"targetId": "new-target"})  # type: ignore[method-assign]
    relay_service.extension_ws = FakeWebSocket()  # type: ignore[assignment]
    relay_service.connected_targets["session-1"] = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(targetId="target-1", title="Old", url="about:blank"),
    )
    relay_service.named_pages["demo"] = "session-1"

    await relay_service.handle_target_info_changed(
        {"targetId": "target-1", "type": "page", "title": "New", "url": "https://example.com"}
    )
    assert relay_service.connected_targets["session-1"].target_info.title == "New"

    await relay_service.handle_target_detached("session-1")
    assert "session-1" not in relay_service.connected_targets

    assert await relay_service.delete_named_page("demo") is False

    result = await relay_service.get_or_create_named_page("new", "localhost", 3002)
    assert result is None


@pytest.mark.asyncio
async def test_target_detached_removes_only_first_named_mapping_due_to_current_logic(relay_service: RelayService) -> None:
    relay_service.send_to_playwright = AsyncMock()  # type: ignore[method-assign]
    relay_service.named_pages["first"] = "session-1"
    relay_service.named_pages["second"] = "session-2"
    relay_service.connected_targets["session-1"] = ConnectedTarget(
        session_id="session-1",
        target_id="target-1",
        target_info=TargetInfo(targetId="target-1"),
    )

    await relay_service.handle_target_detached("session-1")

    assert "first" not in relay_service.named_pages
    assert "second" in relay_service.named_pages


@pytest.mark.asyncio
async def test_named_pages_helpers_and_target_info_changed_unknown_target(relay_service: RelayService) -> None:
    relay_service.send_to_playwright = AsyncMock()  # type: ignore[method-assign]
    relay_service.named_pages["demo"] = "session-1"

    assert relay_service.get_named_pages() == ["demo"]
    assert await relay_service.delete_named_page("demo") is True
    assert await relay_service.delete_named_page("demo") is False

    await relay_service.handle_target_info_changed({"targetId": "missing", "title": "New"})
    relay_service.send_to_playwright.assert_awaited()


def test_target_info_to_dict_exposes_alias_fields(relay_service: RelayService) -> None:
    info = TargetInfo(
        targetId="target-1",
        type="page",
        title="Demo",
        url="https://example.com",
        attached=True,
        browserContextId="ctx-1",
    )

    assert relay_service._target_info_to_dict(info) == {
        "targetId": "target-1",
        "type": "page",
        "title": "Demo",
        "url": "https://example.com",
        "attached": True,
        "browserContextId": "ctx-1",
    }
