"""Marketplace local history unit tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.config.settings import get_settings
from app.modules.marketplace.models import MarketplaceLocalHistoryRestoreRequest
from app.modules.marketplace.request import MarketplaceRequest
from app.modules.version_control.local_history import ManagerLocalHistoryService


@pytest.fixture()
def marketplace_workflows(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETPLACE_STORAGE_PATH", str(tmp_path / "marketplace"))
    monkeypatch.setenv("MANAGER_LOCAL_HISTORY_DIR", str(tmp_path / "local-history"))
    get_settings.cache_clear()
    try:
        yield MarketplaceRequest.create()
    finally:
        get_settings.cache_clear()


def test_marketplace_registry_snapshot_uses_marketplace_domain(tmp_path: Path) -> None:
    source = tmp_path / "registry" / "codex" / "plugins" / "demo" / "README.md"
    source.parent.mkdir(parents=True)
    source.write_text("before", encoding="utf-8")
    history = ManagerLocalHistoryService(history_root=tmp_path / "history")

    entry = history.snapshot_file(
        domain="marketplace",
        resource_id="registry",
        source_path=source,
        relative_path="codex/plugins/demo/README.md",
        operation="write",
    )

    assert entry is not None
    assert entry["domain"] == "marketplace"
    assert entry["resourceId"] == "registry"


def test_marketplace_local_history_uses_revision_fields(tmp_path: Path) -> None:
    source = tmp_path / "registry" / "codex" / "plugins" / "demo" / "README.md"
    source.parent.mkdir(parents=True)
    source.write_text("before", encoding="utf-8")
    history = ManagerLocalHistoryService(history_root=tmp_path / "history")

    entry = history.snapshot_file(
        domain="marketplace",
        resource_id="registry",
        source_path=source,
        relative_path="codex/plugins/demo/README.md",
        operation="write",
        version_id_before="before-revision",
    )

    assert entry is not None
    assert entry["revisionBefore"] == "before-revision"
    assert entry["revisionAfter"] is None
    assert "versionIdBefore" not in entry
    assert "versionIdAfter" not in entry
    assert "contentHashBefore" not in entry
    assert "contentHashAfter" not in entry


def test_marketplace_restore_request_accepts_revision_only() -> None:
    request = MarketplaceLocalHistoryRestoreRequest.model_validate(
        {"revision": "rev-1"}
    )

    assert request.revision == "rev-1"


def test_marketplace_registry_restore_returns_revision(
    marketplace_workflows,
    tmp_path: Path,
) -> None:
    marketplace_workflows.initialize_registry(user_id="user-1")
    target = tmp_path / "marketplace" / "registry" / "README.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("before", encoding="utf-8")
    history = ManagerLocalHistoryService(history_root=tmp_path / "local-history")
    entry = history.snapshot_file(
        domain="marketplace",
        resource_id="registry",
        source_path=target,
        relative_path="README.md",
        operation="write",
    )
    assert entry is not None
    target.write_text("after", encoding="utf-8")
    current_revision = hashlib.sha256(b"after").hexdigest()

    result = marketplace_workflows.restore_registry_file_history(
        "user-1", entry_id=entry["id"], revision=current_revision
    )

    assert result["path"] == "README.md"
    assert result["revision"] == hashlib.sha256(b"before").hexdigest()
    assert "versionId" not in result
