from __future__ import annotations

from app.utils.container_discovery import BrowserContainerDiscovery, BrowserContainerInfo


def test_browser_container_info_to_dict() -> None:
    info = BrowserContainerInfo(
        container_name="browser-1",
        webrtc_internal_url="http://browser-1:6080",
        cdp_url="http://browser-1:9223",
    )

    assert info.to_dict() == {
        "container_name": "browser-1",
        "webrtc_internal_url": "http://browser-1:6080",
        "cdp_url": "http://browser-1:9223",
    }


def test_get_browser_info_uses_environment_defaults(monkeypatch) -> None:
    monkeypatch.delenv(BrowserContainerDiscovery.ENV_CONTAINER_NAME, raising=False)
    monkeypatch.delenv(BrowserContainerDiscovery.ENV_WEBRTC_INTERNAL_URL, raising=False)
    monkeypatch.delenv(BrowserContainerDiscovery.ENV_CDP_URL, raising=False)
    monkeypatch.setenv("WORKSPACE_ID", "ws-123")

    info = BrowserContainerDiscovery.get_browser_info()

    assert info.container_name == "workspace-browser-ws-123"
    assert info.webrtc_internal_url == "http://workspace-browser-ws-123:6080"
    assert info.cdp_url == "http://workspace-browser-ws-123:9223"


def test_is_browser_available_requires_container_and_cdp(monkeypatch) -> None:
    monkeypatch.setenv(BrowserContainerDiscovery.ENV_CONTAINER_NAME, "browser-x")
    monkeypatch.setenv(BrowserContainerDiscovery.ENV_CDP_URL, "http://browser-x:9223")
    monkeypatch.delenv(BrowserContainerDiscovery.ENV_WEBRTC_INTERNAL_URL, raising=False)

    assert BrowserContainerDiscovery.is_browser_available() is True


def test_get_mcp_config_builds_default_cdp_url_when_missing(monkeypatch) -> None:
    monkeypatch.setenv(BrowserContainerDiscovery.ENV_CONTAINER_NAME, "browser-x")
    monkeypatch.delenv(BrowserContainerDiscovery.ENV_CDP_URL, raising=False)
    monkeypatch.delenv(BrowserContainerDiscovery.ENV_WEBRTC_INTERNAL_URL, raising=False)

    assert BrowserContainerDiscovery.get_mcp_config() == {
        "chrome-devtools": {
            "type": "http",
            "url": "http://browser-x:9223",
            "headers": {"User-Agent": "claude-code"},
        }
    }


def test_get_mcp_config_includes_chrome_devtools(monkeypatch) -> None:
    monkeypatch.setenv(BrowserContainerDiscovery.ENV_CONTAINER_NAME, "browser-x")
    monkeypatch.setenv(BrowserContainerDiscovery.ENV_CDP_URL, "http://browser-x:9223")

    assert BrowserContainerDiscovery.get_mcp_config() == {
        "chrome-devtools": {
            "type": "http",
            "url": "http://browser-x:9223",
            "headers": {"User-Agent": "claude-code"},
        }
    }
