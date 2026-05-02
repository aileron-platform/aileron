from __future__ import annotations

import pytest

from app.modules.agent_session.services.tools.codex.sdk_compat import assert_sdk_structure


def test_assert_sdk_structure_passes_with_vendored_sdk() -> None:
    assert_sdk_structure()


def test_assert_sdk_structure_raises_when_async_sync_attr_disappears(monkeypatch) -> None:
    from codex_app_server.async_client import AsyncAppServerClient

    def replacement_init(self, sync_client):
        self.sync_client = sync_client

    monkeypatch.setattr(AsyncAppServerClient, "__init__", replacement_init)

    with pytest.raises(RuntimeError, match="AsyncAppServerClient._sync"):
        assert_sdk_structure()
