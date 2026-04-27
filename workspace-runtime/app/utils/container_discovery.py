"""
Browser Container service discovery utility module

Provides functionality to retrieve Browser container connection information from environment variables,
supporting Docker and Kubernetes service discovery.
"""

import os
from typing import Any
from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserContainerInfo:
    """Browser Container connection information"""

    container_name: str | None
    webrtc_internal_url: str | None
    cdp_url: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "container_name": self.container_name,
            "webrtc_internal_url": self.webrtc_internal_url,
            "cdp_url": self.cdp_url,
        }


class BrowserContainerDiscovery:
    """Browser Container service discovery class

    Read Browser container connection information from environment variables.
    Environment variables are injected by workspace-manager when starting workspace-runtime.

    Environment Variables:
        BROWSER_CONTAINER_NAME: Browser container name (Docker) or Service name (K8s)
        BROWSER_WEBRTC_INTERNAL_URL: Browser WebRTC (neko) internal URL
        BROWSER_CDP_URL: Browser CDP URL
    """

    # Environment variable name constants
    ENV_CONTAINER_NAME = "BROWSER_CONTAINER_NAME"
    ENV_WEBRTC_INTERNAL_URL = "BROWSER_WEBRTC_INTERNAL_URL"
    ENV_CDP_URL = "BROWSER_CDP_URL"

    @classmethod
    def get_browser_info(cls) -> BrowserContainerInfo:
        """Get Browser container connection information

        Read from environment variables, if not set, try to infer from CONTAINER_NAME.

        Returns:
            BrowserContainerInfo: Browser container connection information
        """
        workspace_id = os.getenv("WORKSPACE_ID", "default")
        container_name = os.getenv(cls.ENV_CONTAINER_NAME)

        # If container_name is not set, try to infer from WORKSPACE_ID
        if not container_name and workspace_id:
            container_name = f"workspace-browser-{workspace_id}"

        webrtc_internal_url = os.getenv(cls.ENV_WEBRTC_INTERNAL_URL)
        cdp_url = os.getenv(cls.ENV_CDP_URL)

        # If URL is not set, build default value using container_name
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
        """Get CDP endpoint

        Returns:
            str: CDP URL, or None if unavailable
        """
        info = cls.get_browser_info()
        return info.cdp_url

    @classmethod
    def get_browser_container_name(cls) -> str | None:
        """Get Browser container name

        Returns:
            str: Container name, or None if unavailable
        """
        info = cls.get_browser_info()
        return info.container_name

    @classmethod
    def is_browser_available(cls) -> bool:
        """Check if Browser container is available

        Returns:
            bool: True if Browser container information is complete
        """
        info = cls.get_browser_info()
        return all([
            info.container_name is not None,
            info.cdp_url is not None,
        ])

    @classmethod
    def get_mcp_config(cls) -> dict[str, Any]:
        """Get MCP server configuration example

        Returns:
            dict: MCP configuration dictionary, can be used to build .claude/mcp.json
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


# Backward compatible aliases
ChromeContainerInfo = BrowserContainerInfo
ChromeContainerDiscovery = BrowserContainerDiscovery


__all__ = [
    "BrowserContainerDiscovery",
    "BrowserContainerInfo",
    # Backward compatible aliases
    "ChromeContainerDiscovery",
    "ChromeContainerInfo",
]
