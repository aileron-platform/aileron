from __future__ import annotations

from app.modules.client_browser_relay.models import (
    CreatePageResponse,
    PlaywrightClient,
    RelayStatusResponse,
    TargetInfo,
)


def test_target_info_supports_alias_fields() -> None:
    info = TargetInfo.model_validate(
        {
            "targetId": "target-1",
            "type": "page",
            "title": "Demo",
            "url": "about:blank",
            "browserContextId": "ctx-1",
        }
    )

    assert info.target_id == "target-1"
    assert info.browser_context_id == "ctx-1"
    assert info.model_dump(by_alias=True)["targetId"] == "target-1"


def test_response_models_dump_aliases() -> None:
    relay = RelayStatusResponse(
        wsEndpoint="ws://localhost:3002/api/v1/client-browser-relay/cdp",
        extensionConnected=True,
        connectedTargetsCount=2,
        playwrightClientsCount=1,
    )
    page = CreatePageResponse(
        wsEndpoint="ws://localhost:3002/api/v1/client-browser-relay/cdp",
        name="demo",
        targetId="target-1",
        url="about:blank",
    )

    assert relay.model_dump(by_alias=True)["wsEndpoint"].startswith("ws://")
    assert page.model_dump(by_alias=True)["targetId"] == "target-1"


def test_playwright_client_defaults_to_empty_known_targets() -> None:
    client = PlaywrightClient(id="client-1")

    assert client.known_targets == set()
