from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.template_canonical import CanonicalTarget, InstallPlan
from app.services.template_artifact_cache_service import TemplateArtifactCacheService


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def artifact_cache_service(tmp_path):
    with patch("app.services.template_base_service.get_settings") as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
        service = TemplateArtifactCacheService(MagicMock())
        service.storage_path = tmp_path
        service.cache_root = tmp_path / ".canonical-cache"
        service.manifest_root = tmp_path / ".install-manifests"
        service.cache_root.mkdir(parents=True, exist_ok=True)
        service.manifest_root.mkdir(parents=True, exist_ok=True)
        return service


@pytest.mark.unit
def test_compute_source_hash_changes_when_files_change(artifact_cache_service, tmp_path):
    template_root = tmp_path / "templates" / "demo-template"
    _write(template_root / "template.yaml", "id: demo-template\nname: Demo\nversion: 1.0.0\nschemaVersion: v0\n")

    original_hash = artifact_cache_service.compute_source_hash(template_root)
    _write(template_root / "agents.md", "# rules\n")
    changed_hash = artifact_cache_service.compute_source_hash(template_root)

    assert original_hash != changed_hash


@pytest.mark.unit
def test_save_and_load_compile_cache_round_trip(artifact_cache_service):
    plan = InstallPlan(target=CanonicalTarget.CLAUDE_CODE, installHints={"agentsMdContent": "# rules"})

    stored = artifact_cache_service.save_compile_cache(
        "demo-template",
        CanonicalTarget.CLAUDE_CODE.value,
        "hash123",
        plan,
    )
    loaded = artifact_cache_service.load_compile_cache(
        "demo-template",
        CanonicalTarget.CLAUDE_CODE.value,
        "hash123",
    )

    assert stored.source_hash == "hash123"
    assert loaded is not None
    assert loaded.source_hash == "hash123"
    assert loaded.cache_key == "demo-template:claude-code:hash123"


@pytest.mark.unit
def test_record_install_manifest_persists_install_metadata(artifact_cache_service):
    plan = InstallPlan(
        target=CanonicalTarget.CLAUDE_CODE,
        installHints={},
        sourceHash="hash123",
        cacheKey="demo-template:claude-code:hash123",
    )

    artifact_cache_service.record_install_manifest(
        workspace_id="workspace-1",
        template_id="demo-template",
        target=CanonicalTarget.CLAUDE_CODE.value,
        plan=plan,
    )
    manifest = artifact_cache_service.load_install_manifest("workspace-1", "demo-template")

    assert manifest is not None
    assert manifest["workspaceId"] == "workspace-1"
    assert manifest["templateId"] == "demo-template"
    assert manifest["sourceHash"] == "hash123"
