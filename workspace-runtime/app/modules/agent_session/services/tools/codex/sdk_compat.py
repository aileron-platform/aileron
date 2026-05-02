"""Compatibility checks for the vendored Codex SDK."""

from __future__ import annotations


def assert_sdk_structure() -> None:
    """Raise if the SDK private attributes used by the integration changed."""
    from codex_app_server import AsyncCodex
    from codex_app_server.async_client import AsyncAppServerClient
    from codex_app_server.client import AppServerClient

    if "_client" not in AsyncCodex.__init__.__code__.co_names:
        raise RuntimeError("AsyncCodex._client missing; SDK structure changed")

    if "_sync" not in AsyncAppServerClient.__init__.__code__.co_names:
        raise RuntimeError("AsyncAppServerClient._sync missing; SDK structure changed")

    sample = AppServerClient(approval_handler=lambda *_: {})
    if not callable(getattr(sample, "_approval_handler", None)):
        raise RuntimeError("AppServerClient._approval_handler missing or non-callable")
