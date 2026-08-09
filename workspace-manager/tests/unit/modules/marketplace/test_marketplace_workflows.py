"""Marketplace deep workflow module tests."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from aileron_git_core import (
    GitCommandResult,
    RemoteBranchList,
    VersionControlApplication,
    VersionControlError,
)
from fastapi import HTTPException
from redis.exceptions import ConnectionError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.modules.marketplace.workflows.registry_git as marketplace_registry_git_module
from app.config.settings import get_settings
from app.db.database import Base
from app.modules.marketplace.models import (
    MarketplaceDocumentMutationRequest,
    MarketplaceDocumentRemoveRequest,
    MarketplaceDocumentRenameRequest,
    MarketplaceImportRequest,
    MarketplaceImportSource,
    MarketplaceMcpServerCreateRequest,
    MarketplaceMcpServerDeleteRequest,
    MarketplaceMcpServerMutationRequest,
    MarketplacePackageCreateRequest,
    MarketplacePackageDeleteRequest,
    MarketplacePackageFile,
    MarketplacePackageSaveRequest,
    MarketplaceRegistryCloneRequest,
    MarketplaceRegistryRootMetadataSavePayload,
)
from app.modules.marketplace.request import MarketplaceRequest


class _RecordingResourceWriteLocks:
    def __init__(self) -> None:
        self.events: list[tuple[str, tuple]] = []
        self.active_keys: list[tuple] = []

    def lock(self, key: tuple):
        recorder = self

        class _Lock:
            def __enter__(self):
                recorder.events.append(("enter", key))
                recorder.active_keys.append(key)
                return self

            def __exit__(self, _exc_type, _exc, _tb):
                recorder.active_keys.remove(key)
                recorder.events.append(("exit", key))
                return False

        return _Lock()

    def is_active(self, key: tuple) -> bool:
        return key in self.active_keys


class _FailOnceDeleteRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.fail_next_overview_delete = False

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, *, ex: int) -> None:
        _ = ex
        self.values[key] = value

    def delete(self, *keys: str) -> None:
        if self.fail_next_overview_delete and any(
            key.endswith(":overview") for key in keys
        ):
            self.fail_next_overview_delete = False
            raise ConnectionError("transient delete failure")
        for key in keys:
            self.values.pop(key, None)

    def scan_iter(self, *, match: str, count: int):
        _ = count
        prefix, suffix = match.split("*", 1)
        return (
            key
            for key in list(self.values)
            if key.startswith(prefix) and key.endswith(suffix)
        )


@pytest.fixture()
def marketplace_workflows(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETPLACE_STORAGE_PATH", str(tmp_path / "marketplace"))
    monkeypatch.setenv("MANAGER_LOCAL_HISTORY_DIR", str(tmp_path / "local-history"))
    get_settings.cache_clear()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield MarketplaceRequest.create(session)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        get_settings.cache_clear()


def _metadata(
    name: str = "Team Marketplace",
) -> MarketplaceRegistryRootMetadataSavePayload:
    return MarketplaceRegistryRootMetadataSavePayload(
        name=name,
        owner={
            "name": "Team Maintainer",
            "email": "team@example.local",
        },
        description="Team package registry",
    )


def test_document_mutations_return_canonical_identity(
    marketplace_workflows,
) -> None:
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="documents",
            display_name="Documents",
            description="Document mutation contract",
        ),
    )

    created_document = marketplace_workflows.create_document(
        "user-1",
        "codex",
        "documents",
        "commands",
        MarketplaceDocumentMutationRequest(
            revision=created.revision,
            path="prompts/review.md",
            content="# Review\n",
        ),
    )
    assert created_document.path == "prompts/review.md"
    assert created_document.revision != created.revision
    assert created_document.owner_file_path is None
    assert created_document.base_entry_fingerprint is None

    moved_document = marketplace_workflows.move_document(
        "user-1",
        "codex",
        "documents",
        "commands",
        MarketplaceDocumentRenameRequest(
            revision=created_document.revision,
            previous_path="prompts/review.md",
            next_path="prompts/team-review.md",
        ),
    )
    assert moved_document.path == "prompts/team-review.md"
    assert moved_document.revision != created_document.revision

    deleted_document = marketplace_workflows.remove_document(
        "user-1",
        "codex",
        "documents",
        "commands",
        MarketplaceDocumentRemoveRequest(
            revision=moved_document.revision,
            path="prompts/team-review.md",
        ),
    )
    assert deleted_document.path == "prompts/team-review.md"
    assert deleted_document.revision != moved_document.revision
    assert deleted_document.base_entry_fingerprint is None


def test_hooks_sources_round_trip_without_relocating_manifest_referenced_files(
    marketplace_workflows,
) -> None:
    marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="hooks",
            display_name="Hooks",
            description="Marketplace hooks source contract",
        ),
    )
    package_path = (
        Path(get_settings().MARKETPLACE_STORAGE_PATH)
        / "registry"
        / "codex"
        / "plugins"
        / "hooks"
    )
    manifest_path = package_path / ".codex-plugin" / "plugin.json"
    first_path = package_path / "hooks" / "first.json"
    second_path = package_path / "hooks" / "second.json"
    first_document = {
        "hooks": {"SessionStart": [{"type": "command", "command": "echo first"}]},
        "metadata": {"keep": "first"},
    }
    second_document = {
        "hooks": {"Stop": [{"type": "command", "command": "echo second"}]},
        "metadata": {"keep": "second"},
    }
    manifest_path.write_text(
        json.dumps(
            {
                "name": "hooks",
                "version": "0.1.0",
                "description": "Marketplace hooks source contract",
                "hooks": ["hooks/first.json", "hooks/second.json"],
            }
        ),
        encoding="utf-8",
    )
    first_path.parent.mkdir(parents=True, exist_ok=True)
    first_path.write_text(json.dumps(first_document), encoding="utf-8")
    second_path.write_text(json.dumps(second_document), encoding="utf-8")
    marketplace_workflows.refresh_package_overview("user-1", "codex", "hooks")

    resource = marketplace_workflows.get_hooks("user-1", "codex", "hooks")
    sources = {source["path"]: source for source in resource["sources"]}
    assert set(sources) == {"hooks/first.json", "hooks/second.json"}
    assert sources["hooks/first.json"]["nativeContent"] == first_document["hooks"]

    updated_first_document = {
        "hooks": {"SessionEnd": [{"type": "command", "command": "echo updated"}]},
        "metadata": {"keep": "updated"},
    }
    result = marketplace_workflows.update_hooks(
        "user-1",
        "codex",
        "hooks",
        resource["revision"],
        sources["hooks/first.json"]["sourceId"],
        json.dumps(updated_first_document),
    )

    assert result.path == "hooks/first.json"
    assert json.loads(first_path.read_text(encoding="utf-8")) == {
        "hooks": updated_first_document["hooks"],
        "metadata": first_document["metadata"],
    }
    assert json.loads(second_path.read_text(encoding="utf-8")) == second_document


def test_mcp_mutations_return_owner_and_entry_fingerprint(
    marketplace_workflows,
) -> None:
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="mcp-contract",
            display_name="MCP Contract",
            description="MCP mutation contract",
        ),
    )

    created_server = marketplace_workflows.create_mcp_server(
        "user-1",
        "codex",
        "mcp-contract",
        MarketplaceMcpServerCreateRequest(
            revision=created.revision,
            name="database",
            server={"command": "node", "args": ["server.js"]},
        ),
    )
    assert created_server.path == ".mcp.json"
    assert created_server.owner_file_path == ".mcp.json"
    assert created_server.base_entry_fingerprint

    saved_server = marketplace_workflows.save_mcp_server(
        "user-1",
        "codex",
        "mcp-contract",
        "database",
        MarketplaceMcpServerMutationRequest(
            revision=created_server.revision,
            server={"command": "node", "args": ["server-v2.js"]},
            owner_file_path=created_server.owner_file_path,
            base_entry_fingerprint=created_server.base_entry_fingerprint,
        ),
    )
    assert saved_server.path == ".mcp.json"
    assert saved_server.owner_file_path == ".mcp.json"
    assert saved_server.base_entry_fingerprint != created_server.base_entry_fingerprint

    deleted_server = marketplace_workflows.delete_mcp_server(
        "user-1",
        "codex",
        "mcp-contract",
        "database",
        MarketplaceMcpServerDeleteRequest(
            revision=saved_server.revision,
            owner_file_path=saved_server.owner_file_path,
            base_entry_fingerprint=saved_server.base_entry_fingerprint,
        ),
    )
    assert deleted_server.path == ".mcp.json"
    assert deleted_server.owner_file_path == ".mcp.json"
    assert deleted_server.base_entry_fingerprint is None


def test_registry_git_status_maps_shared_application_errors(
    marketplace_workflows, monkeypatch
):
    marketplace_workflows.initialize_git_repository("user-1")

    workflow = marketplace_workflows._operations["get_registry_changes"].__self__
    monkeypatch.setattr(
        workflow.version_control,
        "read",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            VersionControlError("file_conflict")
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.get_registry_changes("user-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["errorCode"] == "file_conflict"
    assert exc_info.value.detail["messageKey"] == "file_conflict"


def test_registry_file_diff_rejects_paths_outside_registry(marketplace_workflows):
    marketplace_workflows.initialize_git_repository("user-1")

    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.get_registry_file_diff("user-1", "../outside.json")

    assert exc_info.value.status_code == 400


def test_clone_registry_rejects_credentials_before_git_clone(
    marketplace_workflows,
    monkeypatch,
):
    remote_url = "https://topsecret@gitlab.example/marketplaces/private.git"

    def unexpected_git(*_args, **_kwargs):
        pytest.fail("credential-bearing Registry remote must not reach git clone")

    monkeypatch.setattr(VersionControlApplication, "execute", unexpected_git)

    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.clone_registry(
            "user-1",
            MarketplaceRegistryCloneRequest(remoteUrl=remote_url),
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["errorCode"] == "VC_REMOTE_URL_CREDENTIALS_NOT_ALLOWED"


def test_clone_registry_ssh_requires_system_user_key_before_git_clone(
    marketplace_workflows,
    monkeypatch,
):
    def unexpected_git(*_args, **_kwargs):
        pytest.fail("SSH clone without a system user key must not reach git")

    monkeypatch.setattr(VersionControlApplication, "execute", unexpected_git)

    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.clone_registry(
            "user-1",
            MarketplaceRegistryCloneRequest(
                remoteUrl="git@example.invalid:team/marketplace.git"
            ),
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["errorCode"] == "VC_SSH_KEY_REQUIRED"


def test_remote_branches_uses_user_credentials_and_returns_default_branch(
    marketplace_workflows,
    monkeypatch,
):
    recorded: dict[str, object] = {}

    def fake_discover_remote_branches(
        db,
        *,
        user_id,
        repo_root,
        remote_url,
    ):
        recorded.update(
            {
                "db": db,
                "user_id": user_id,
                "repo_root": repo_root,
                "remote_url": remote_url,
            }
        )
        return RemoteBranchList(
            branches=["main", "develop"],
            default_branch="main",
        )

    monkeypatch.setattr(
        marketplace_registry_git_module,
        "discover_remote_branches",
        fake_discover_remote_branches,
    )

    result = marketplace_workflows.remote_branches(
        "user-1",
        "git@example.invalid:team/marketplace.git",
    )

    assert recorded["db"] is marketplace_workflows._db
    assert recorded["user_id"] == "user-1"
    assert recorded["remote_url"] == (
        "git@example.invalid:team/marketplace.git"
    )
    assert Path(recorded["repo_root"]).is_dir()
    assert result.branches == ["main", "develop"]
    assert result.default_branch == "main"


def test_initialize_registry_rejects_an_existing_repository(
    marketplace_workflows,
):
    first = marketplace_workflows.initialize_git_repository("user-1")
    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.initialize_git_repository("user-1")

    assert first.isInitialized is True
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["errorCode"] == "repository_dirty"


def test_save_package_uses_manifest_as_description_authority(marketplace_workflows):
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Original package",
        ),
    )

    marketplace_workflows.save_package(
        "user-1",
        "codex",
        "figma-context",
        MarketplacePackageSaveRequest(
            provider="codex",
            packageId="figma-context",
            revision=created.revision,
            listing={
                "name": "figma-context",
                "source": {
                    "source": "local",
                    "path": "./plugins/figma-context",
                },
                "description": "Catalog description",
            },
            manifest={
                "name": "figma-context",
                "version": "0.1.0",
                "description": "Manifest description",
            },
            readmeMarkdown="# Figma Context\n",
            packageFiles=[
                MarketplacePackageFile(
                    path=".codex-plugin/plugin.json",
                    content=json.dumps(
                        {
                            "name": "figma-context",
                            "version": "0.1.0",
                            "description": "Manifest description",
                        }
                    ),
                    binary=False,
                ),
                MarketplacePackageFile(
                    path="README.md",
                    content="# Figma Context\n",
                    binary=False,
                ),
            ],
        ),
    )

    detail = marketplace_workflows.get_package_detail(
        "user-1", "codex", "figma-context"
    )
    assert detail is not None
    assert detail.catalog_metadata["description"] == "Manifest description"
    assert detail.manifest_metadata["description"] == "Manifest description"


def test_marketplace_tree_lists_include_entry_type(marketplace_workflows):
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    marketplace_workflows.create_skill_entry(
        "user-1",
        "codex",
        "figma-context",
        created.revision,
        "skills/example",
        "directory",
    )
    detail = marketplace_workflows.get_package_detail(
        "user-1", "codex", "figma-context"
    )
    assert detail is not None
    marketplace_workflows.write_skill_file(
        "user-1",
        "codex",
        "figma-context",
        detail.revision,
        "skills/example/SKILL.md",
        "# Skill",
    )
    detail = marketplace_workflows.get_package_detail(
        "user-1", "codex", "figma-context"
    )
    assert detail is not None
    marketplace_workflows.write_package_file(
        "user-1",
        "codex",
        "figma-context",
        detail.revision,
        "docs/readme.md",
        "# Readme",
    )

    skill_entries = marketplace_workflows.list_skill_files(
        "user-1", "codex", "figma-context"
    )
    file_entries = marketplace_workflows.list_package_files_tree(
        "user-1", "codex", "figma-context"
    )

    skill_nodes = [
        {"path": item["path"], "name": item["name"], "type": item["type"]}
        for item in skill_entries["nodes"]
    ]
    file_nodes = [
        {"path": item["path"], "name": item["name"], "type": item["type"]}
        for item in file_entries["nodes"]
    ]
    assert {
        "path": "skills/example",
        "name": "example",
        "type": "directory",
    } in skill_nodes
    assert {
        "path": "skills/example/SKILL.md",
        "name": "SKILL.md",
        "type": "file",
    } in skill_nodes
    assert {"path": "docs", "name": "docs", "type": "directory"} in file_nodes
    assert {"path": "docs/readme.md", "name": "readme.md", "type": "file"} in file_nodes


def test_validate_import_source_rejects_unsafe_git_inputs(marketplace_workflows):
    with pytest.raises(HTTPException) as token_exc:
        marketplace_workflows.validate_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="codex",
                sourceKind="git",
                source="https://token@example.com/org/repo.git",
            ),
        )
    with pytest.raises(HTTPException) as key_exc:
        marketplace_workflows.validate_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="codex",
                sourceKind="git",
                source="-----BEGIN OPENSSH PRIVATE KEY-----",
            ),
        )

    assert (
        token_exc.value.detail["errorCode"]
        == "marketplace.import.validation.https_token_unsupported"
    )
    assert (
        key_exc.value.detail["errorCode"]
        == "marketplace.import.validation.raw_private_key_unsupported"
    )


def test_scan_import_source_clones_github_tree_url_as_repository_url(
    marketplace_workflows,
    monkeypatch,
):
    commands = []

    def fake_git(repo_root, *args, **kwargs):
        commands.append((repo_root, args, kwargs))
        plugin_root = Path(args[-1]) / "plugins" / "frontend-design"
        manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            json.dumps({"name": "frontend-design"}),
            encoding="utf-8",
        )
        return GitCommandResult(args=["git", *args], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.import_sources.git_allow_failure",
        fake_git,
    )

    candidates = marketplace_workflows.scan_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="claude-code",
            sourceKind="git",
            source=(
                "https://github.com/anthropics/claude-code/"
                "tree/main/plugins/frontend-design"
            ),
        ),
    )

    assert [candidate.package_id for candidate in candidates] == ["frontend-design"]
    assert candidates[0].source_path == "."
    assert list(commands[0][1]) == [
        "clone",
        "--depth",
        "1",
        "--branch",
        "main",
        "https://github.com/anthropics/claude-code.git",
        commands[0][1][-1],
    ]


def test_scan_import_source_rejects_missing_github_tree_subpath(
    marketplace_workflows,
    monkeypatch,
):
    commands = []

    def fake_git(repo_root, *args, **kwargs):
        commands.append((repo_root, args, kwargs))
        Path(args[-1]).mkdir(parents=True)
        return GitCommandResult(args=["git", *args], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.import_sources.git_allow_failure",
        fake_git,
    )

    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.scan_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="claude-code",
                sourceKind="git",
                source=(
                    "https://github.com/anthropics/claude-code/"
                    "tree/main/plugins/missing"
                ),
            ),
        )

    assert (
        exc_info.value.detail["errorCode"]
        == "marketplace.import.validation.invalid_repository_url"
    )
    assert not Path(commands[0][1][-1]).exists()


def test_save_uploaded_import_source_rejects_zip_slip_entry(marketplace_workflows):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../escape.txt", "bad")

    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.save_uploaded_import_source(
            "user-1",
            "codex",
            "marketplace.zip",
            buffer.getvalue(),
        )

    assert exc_info.value.detail["errorCode"] == "marketplace.validation.path_escape"


def test_export_package_requires_current_revision(marketplace_workflows):
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        marketplace_workflows.export_package(
            "user-1", "codex", created.package_id, "stale"
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "marketplace.package.revision_conflict"


def test_export_package_allows_created_scaffold_package(marketplace_workflows):
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="draft-only",
            display_name="Draft Only",
            description="Draft package",
        ),
    )

    archive = marketplace_workflows.export_package(
        "user-1", "codex", created.package_id, created.revision
    )

    assert archive


@pytest.mark.parametrize(
    ("provider", "package_id", "expected_entries"),
    [
        (
            "claude-code",
            "review-assistant",
            {
                ".claude-plugin/marketplace.json",
                "plugins/review-assistant/.claude-plugin/plugin.json",
            },
        ),
        (
            "codex",
            "figma-context",
            {
                ".agents/plugins/marketplace.json",
                "plugins/figma-context/.codex-plugin/plugin.json",
            },
        ),
    ],
)
def test_export_package_archives_scan_and_import_round_trip(
    marketplace_workflows,
    provider,
    package_id,
    expected_entries,
):
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider=provider,
            package_id=package_id,
            display_name="Exported Package",
            description="Exported package",
        ),
    )
    archive_bytes = marketplace_workflows.export_package(
        "user-1", provider, package_id, created.revision
    )

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
    assert expected_entries.issubset(names)

    marketplace_workflows.delete_package(
        "user-1",
        MarketplacePackageDeleteRequest(
            provider=provider,
            package_id=package_id,
            revision=created.revision,
        ),
    )
    upload = marketplace_workflows.save_uploaded_import_source(
        "user-1",
        provider,
        f"{provider}-{package_id}.zip",
        archive_bytes,
    )
    candidates = marketplace_workflows.scan_import_source("user-1", upload.source)
    result = marketplace_workflows.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=upload.source, candidates=candidates),
    )

    assert [candidate.package_id for candidate in candidates] == [package_id]
    assert [item.package_id for item in result.imported] == [package_id]
    assert result.failed == []
    assert (
        marketplace_workflows.get_package_detail("user-1", provider, package_id)
        is not None
    )


def test_exported_archive_duplicate_actions_use_import_flow(marketplace_workflows):
    created = marketplace_workflows.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    archive_bytes = marketplace_workflows.export_package(
        "user-1", "codex", "figma-context", created.revision
    )
    upload = marketplace_workflows.save_uploaded_import_source(
        "user-1",
        "codex",
        "codex-figma-context.zip",
        archive_bytes,
    )

    skipped_candidate = marketplace_workflows.scan_import_source(
        "user-1", upload.source
    )[0]
    skipped = marketplace_workflows.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=upload.source, candidates=[skipped_candidate]),
    )
    assert skipped.imported == []
    assert [candidate.package_id for candidate in skipped.skipped] == ["figma-context"]

    overwrite_candidate = marketplace_workflows.scan_import_source(
        "user-1", upload.source
    )[0].model_copy(
        update={
            "duplicate_action": "overwrite",
        }
    )
    overwritten = marketplace_workflows.import_candidates(
        "user-1",
        MarketplaceImportRequest(
            source=upload.source, candidates=[overwrite_candidate]
        ),
    )
    assert [item.package_id for item in overwritten.imported] == ["figma-context"]

    copy_candidate = marketplace_workflows.scan_import_source("user-1", upload.source)[
        0
    ].model_copy(
        update={
            "duplicate_action": "import-as-new",
            "new_package_id": "figma-context-copy",
        }
    )
    copied = marketplace_workflows.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=upload.source, candidates=[copy_candidate]),
    )

    assert [item.package_id for item in copied.imported] == ["figma-context-copy"]
    assert (
        marketplace_workflows.get_package_detail(
            "user-1", "codex", "figma-context-copy"
        )
        is not None
    )


@pytest.mark.unit
def test_get_registry_operation_status_idle_when_no_active_operation(
    marketplace_workflows,
):
    """get_registry_operation_status reports inactive when no mutating op is in flight."""
    result = marketplace_workflows.get_registry_operation_status("user-1")

    assert result.isActive is False
    assert result.operation is None
    assert result.startedAt is None
