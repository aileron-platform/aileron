"""
Browser Container 服務發現工具模組

提供從環境變數中取得 Browser container 連接資訊的功能，
支援 Docker 和 Kubernetes 服務發現。
"""

import os
from typing import Any
from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserContainerInfo:
    """Browser Container 連接資訊"""

    container_name: str | None
    webrtc_internal_url: str | None
    cdp_url: str | None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式"""
        return {
            "container_name": self.container_name,
            "webrtc_internal_url": self.webrtc_internal_url,
            "cdp_url": self.cdp_url,
        }


class BrowserContainerDiscovery:
    """Browser Container 服務發現類別

    從環境變數中讀取 Browser container 的連接資訊。
    環境變數由 workspace-manager 在啟動 workspace-runtime 時注入。

    環境變數:
        BROWSER_CONTAINER_NAME: Browser 容器名稱（Docker）或 Service 名稱（K8s）
        BROWSER_WEBRTC_INTERNAL_URL: Browser WebRTC (neko) 內部 URL
        BROWSER_CDP_URL: Browser CDP URL
    """

    # 環境變數名稱常數
    ENV_CONTAINER_NAME = "BROWSER_CONTAINER_NAME"
    ENV_WEBRTC_INTERNAL_URL = "BROWSER_WEBRTC_INTERNAL_URL"
    ENV_CDP_URL = "BROWSER_CDP_URL"

    @classmethod
    def get_browser_info(cls) -> BrowserContainerInfo:
        """取得 Browser container 連接資訊

        從環境變數讀取，如果環境變數未設定則嘗試從 CONTAINER_NAME 推斷。

        Returns:
            BrowserContainerInfo: Browser container 連接資訊
        """
        workspace_id = os.getenv("WORKSPACE_ID", "default")
        container_name = os.getenv(cls.ENV_CONTAINER_NAME)

        # 如果沒有設定 container_name，嘗試從 WORKSPACE_ID 推斷
        if not container_name and workspace_id:
            container_name = f"workspace-browser-{workspace_id}"

        webrtc_internal_url = os.getenv(cls.ENV_WEBRTC_INTERNAL_URL)
        cdp_url = os.getenv(cls.ENV_CDP_URL)

        # 如果沒有設定 URL，使用 container_name 構建預設值
        if not webrtc_internal_url and container_name:
            webrtc_internal_url = f"http://{container_name}:6080"

        if not cdp_url and container_name:
            cdp_url = f"http://{container_name}:9223"

        return BrowserContainerInfo(
            container_name=container_name,
            webrtc_internal_url=webrtc_internal_url,
            cdp_url=cdp_url,
        )

    @classmethod
    def get_cdp_endpoint(cls) -> str | None:
        """取得 CDP endpoint

        Returns:
            str: CDP URL，如果無法取得則返回 None
        """
        info = cls.get_browser_info()
        return info.cdp_url

    @classmethod
    def get_browser_container_name(cls) -> str | None:
        """取得 Browser container 名稱

        Returns:
            str: Container 名稱，如果無法取得則返回 None
        """
        info = cls.get_browser_info()
        return info.container_name

    @classmethod
    def is_browser_available(cls) -> bool:
        """檢查 Browser container 是否可用

        Returns:
            bool: 如果 Browser container 資訊完整則返回 True
        """
        info = cls.get_browser_info()
        return all([
            info.container_name is not None,
            info.cdp_url is not None,
        ])

    @classmethod
    def get_mcp_config(cls) -> dict[str, Any]:
        """取得 MCP 伺服器配置範例

        Returns:
            dict: MCP 配置字典，可用於構建 .claude/mcp.json
        """
        info = cls.get_browser_info()

        config: dict[str, Any] = {}

        if info.cdp_url:
            config["chrome-devtools"] = {
                "type": "http",
                "url": info.cdp_url,
                "headers": {
                    "User-Agent": "claude-code"
                }
            }

        return config


# 保持向後兼容的別名
ChromeContainerInfo = BrowserContainerInfo
ChromeContainerDiscovery = BrowserContainerDiscovery


__all__ = [
    "BrowserContainerDiscovery",
    "BrowserContainerInfo",
    # 向後兼容別名
    "ChromeContainerDiscovery",
    "ChromeContainerInfo",
]
