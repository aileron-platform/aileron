from __future__ import annotations

import asyncio
import importlib

from app.modules.cli_settings.cache_api import (
    AgentSettingsCacheRefreshRequest,
    AgentSettingsCacheRefreshResponse,
)

cache_router = importlib.import_module("app.modules.cli_settings.cache_api")


def test_refresh_endpoint_forwards_scoped_identity(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_clear(**kwargs) -> None:
        received.update(kwargs)

    monkeypatch.setattr(cache_router, "clear_agent_settings_cache", fake_clear)

    response = asyncio.run(
        cache_router.refresh_agent_settings_cache(
            AgentSettingsCacheRefreshRequest(
                provider="codex",
                capability="skills",
                scope="user",
            ),
            workspace_id="ws-1",
        )
    )

    assert response == AgentSettingsCacheRefreshResponse(refreshed=True)
    assert received == {
        "provider": "codex",
        "workspace_id": "ws-1",
        "capability": "skills",
        "scope": "user",
    }
