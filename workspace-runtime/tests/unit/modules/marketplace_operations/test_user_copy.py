"""Runtime contract tests for package-format-aware standalone User Copy."""

from __future__ import annotations

import os
import stat
import warnings
import zipfile
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aileron_marketplace_core import (
    PluginPackageFormat,
    PluginReleaseIdentity,
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopySourceProfilePreviewContract,
    extract_user_copy_source_profile,
    package_tree_digest,
)

from app.modules.cli_settings.user_scope.planner import UserCopyInventory
from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.user_copy import MarketplaceUserCopyService

_RUNTIME_ID = "11111111-1111-4111-8111-111111111111"
_REVISION = "b" * 64
_OPERATION_ID = "a" * 32


class _Inventory:
    def inventory(self, target_client: str, *, profile: Any = None) -> UserCopyInventory:
        assert target_client in {"claude-code", "codex"}
        assert profile is not None
        return UserCopyInventory(complete=True)


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        AILERON_WORKSPACE_ID="workspace-1",
        AILERON_RUNTIME_INSTANCE_ID=_RUNTIME_ID,
        MARKETPLACE_OPERATION_JOURNAL_DIR=str(tmp_path / "state"),
    )


def _archive(package_root: Path) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for source in sorted(path for path in package_root.rglob("*") if path.is_file()):
            info = zipfile.ZipInfo(source.relative_to(package_root).as_posix())
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if os.access(source, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(info, source.read_bytes())
    return buffer.getvalue()


def _request(
    package_root: Path,
    *,
    package_format: PluginPackageFormat,
    target_client: str,
    catalog_plugin_id: str = "managed/demo",
) -> tuple[UserCopyProjectionPreflightRequestContract, Any]:
    profile = extract_user_copy_source_profile(
        package_format,
        package_root,
        release=PluginReleaseIdentity(
            catalog_plugin_id=catalog_plugin_id,
            revision=_REVISION,
        ),
    )
    preview_payload = profile.canonical_dict()
    preview_payload["profileDigest"] = profile.profile_digest
    preview = UserCopySourceProfilePreviewContract.from_wire(preview_payload)
    request = UserCopyProjectionPreflightRequestContract(
        packageFormat=package_format.value,
        targetClient=target_client,
        catalogPluginId=catalog_plugin_id,
        releaseRevision=_REVISION,
        workspaceId="workspace-1",
        runtimeInstanceId=_RUNTIME_ID,
        expectedSourceDigest=package_tree_digest(package_root),
        expectedProfileVersion=profile.profile_version,
        expectedProfileDigest=profile.profile_digest,
        sourceProfile=preview,
    )
    return request, profile


def _service(tmp_path: Path) -> MarketplaceUserCopyService:
    return MarketplaceUserCopyService(
        settings=_settings(tmp_path),  # type: ignore[arg-type]
        inventory_reader=_Inventory(),  # type: ignore[arg-type]
    )


def test_preflight_returns_exact_format_client_and_root_proofs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "AGENTS.md").write_text("# Instructions\n", encoding="utf-8")
    request, _ = _request(
        package_root,
        package_format=PluginPackageFormat.CODEX_NATIVE,
        target_client="codex",
    )

    result = _service(tmp_path).preflight(request)

    assert result.status == "ready"
    assert result.package_format == "codex-native"
    assert result.target_client == "codex"
    assert result.target_client_state_root_id.startswith("tcsr_")
    assert len(result.projection_digest) == 64
    assert [resource.target_locator for resource in result.resources] == [
        "~/.codex/AGENTS.md"
    ]


def test_preflight_returns_blocked_for_unregistered_projection_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'plugin.schema.json","name":"demo"}',
        encoding="utf-8",
    )
    request, _ = _request(
        package_root,
        package_format=PluginPackageFormat.AGENT_PLUGIN_V1,
        target_client="claude-code",
    )

    result = _service(tmp_path).preflight(request)

    assert result.status == "blocked"
    assert [issue.code for issue in result.blocking_issues] == [
        "marketplace.user_copy.projection_not_supported"
    ]


def test_preflight_reports_unsupported_codex_resource_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / ".codex-plugin").mkdir()
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"demo","apps":["./.app.json"]}',
        encoding="utf-8",
    )
    (package_root / ".app.json").write_text(
        '{"apps":{"demo":{"id":"connector_demo"}}}',
        encoding="utf-8",
    )
    (package_root / "skills" / "review").mkdir(parents=True)
    (package_root / "skills" / "review" / "SKILL.md").write_text(
        "# Review\n",
        encoding="utf-8",
    )
    (package_root / "agents").mkdir()
    (package_root / "agents" / "reviewer.md").write_text(
        "You are the review agent.\n",
        encoding="utf-8",
    )
    request, _ = _request(
        package_root,
        package_format=PluginPackageFormat.CODEX_NATIVE,
        target_client="codex",
    )

    result = _service(tmp_path).preflight(request)

    assert result.status == "confirmation-required"
    skipped = {
        (resource.resource_type, resource.code)
        for resource in result.skipped_resources
    }
    assert ("apps", "unsupported-resource") in skipped
    assert ("subagent", "format-unsupported") in skipped
    assert result.blocking_issues == []


def test_partial_agent_plugin_apply_materializes_projectable_resources_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'plugin.schema.json","name":"demo"}',
        encoding="utf-8",
    )
    skill = package_root / "skills" / "deploy"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Deploy\n", encoding="utf-8")
    (package_root / "mcp.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'mcp.schema.json","mcpServers":{"legacy":{"type":"sse",'
        '"url":"https://example.com/mcp"}}}',
        encoding="utf-8",
    )
    request, profile = _request(
        package_root,
        package_format=PluginPackageFormat.AGENT_PLUGIN_V1,
        target_client="codex",
    )
    service = _service(tmp_path)
    monkeypatch.setattr(service, "_clear_target_client_caches", lambda _client: None)
    preflight = service.preflight(request)
    assert preflight.status == "confirmation-required"
    assert [item.resource_id for item in preflight.skipped_resources] == ["legacy"]
    bundle = _archive(package_root)
    metadata = UserCopyProjectionApplyMetadataContract(
        operationId=_OPERATION_ID,
        packageFormat="agent-plugin/1.0.0",
        targetClient="codex",
        catalogPluginId="managed/demo",
        releaseRevision=_REVISION,
        workspaceId="workspace-1",
        runtimeInstanceId=_RUNTIME_ID,
        targetClientStateRootId=preflight.target_client_state_root_id,
        expectedSourceDigest=package_tree_digest(package_root),
        expectedArchiveDigest=sha256(bundle).hexdigest(),
        expectedPackageTreeDigest=package_tree_digest(package_root),
        expectedProfileVersion=profile.profile_version,
        expectedProfileDigest=profile.profile_digest,
        expectedProjectionDigest=preflight.projection_digest,
        expectedMaterializationDigest=preflight.materialization_digest,
        acceptPartialCopy=True,
        expectedSkippedCount=1,
        overwriteApprovals=[],
    )

    result = service.apply(metadata, bundle)

    assert (home / ".codex" / "skills" / "deploy" / "SKILL.md").is_file()
    assert result.created_count == 1
    assert result.skipped_count == 1


def test_apply_rejects_target_root_change_before_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_home = tmp_path / "home-one"
    first_home.mkdir()
    monkeypatch.setenv("HOME", str(first_home))
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "AGENTS.md").write_text("# Instructions\n", encoding="utf-8")
    request, profile = _request(
        package_root,
        package_format=PluginPackageFormat.CODEX_NATIVE,
        target_client="codex",
    )
    service = _service(tmp_path)
    preflight = service.preflight(request)
    bundle = _archive(package_root)
    metadata = UserCopyProjectionApplyMetadataContract(
        operationId=_OPERATION_ID,
        packageFormat="codex-native",
        targetClient="codex",
        catalogPluginId="managed/demo",
        releaseRevision=_REVISION,
        workspaceId="workspace-1",
        runtimeInstanceId=_RUNTIME_ID,
        targetClientStateRootId=preflight.target_client_state_root_id,
        expectedSourceDigest=package_tree_digest(package_root),
        expectedArchiveDigest=sha256(bundle).hexdigest(),
        expectedPackageTreeDigest=package_tree_digest(package_root),
        expectedProfileVersion=profile.profile_version,
        expectedProfileDigest=profile.profile_digest,
        expectedProjectionDigest=preflight.projection_digest,
        expectedMaterializationDigest=preflight.materialization_digest,
        acceptPartialCopy=False,
        expectedSkippedCount=0,
        overwriteApprovals=[],
    )
    second_home = tmp_path / "home-two"
    second_home.mkdir()
    monkeypatch.setenv("HOME", str(second_home))

    with pytest.raises(MarketplaceOperationError) as error:
        service.apply(metadata, bundle)
    assert error.value.code == "marketplace.user_copy.plan_stale"
