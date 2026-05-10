"""Marketplace service tests."""

from __future__ import annotations

import json
import base64
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config.settings import get_settings
from app.models.marketplace import (
    MarketplaceCliCapabilities,
    MarketplaceCliPreflightResult,
    MarketplaceImportCandidate,
    MarketplaceImportRequest,
    MarketplaceImportSource,
    MarketplaceInstallCommandPlan,
    MarketplaceInstallRequest,
    MarketplaceGitCommitRequest,
    MarketplaceGitPathRequest,
    MarketplacePackageCreateRequest,
    MarketplacePackageDeleteRequest,
    MarketplacePackageSaveRequest,
    MarketplacePackageSummary,
    MarketplaceRegistryCloneRequest,
    MarketplaceRegistryRemoteRequest,
    MarketplaceRegistryRootMetadataSavePayload,
)
from app.services.marketplace_service import (
    MarketplaceConflictError,
    MarketplaceImportSourceError,
    MarketplacePathError,
    MarketplaceService,
    MarketplaceValidationError,
)


@pytest.fixture()
def marketplace_service(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKETPLACE_STORAGE_PATH", str(tmp_path / "marketplace"))
    monkeypatch.setenv("MANAGER_MARKETPLACE_INSTALL_DIR", str(tmp_path / "marketplace-install"))
    get_settings.cache_clear()
    try:
        yield MarketplaceService()
    finally:
        get_settings.cache_clear()


def _metadata(name: str = "Team Marketplace") -> MarketplaceRegistryRootMetadataSavePayload:
    return MarketplaceRegistryRootMetadataSavePayload(
        name=name,
        owner={
            "name": "Team Maintainer",
            "email": "team@example.local",
        },
        description="Team package registry",
    )


def test_initialize_registry_bootstraps_provider_roots_without_gemini_manifest(marketplace_service):
    result = marketplace_service.initialize_registry("user-1", _metadata())
    root = marketplace_service.get_registry_root("user-1")

    assert result.created is True
    assert (root / "claude-code" / ".claude-plugin" / "marketplace.json").exists()
    assert (root / "claude-code" / "plugins").is_dir()
    assert (root / "codex" / ".agents" / "plugins" / "marketplace.json").exists()
    assert (root / "codex" / "plugins").is_dir()
    assert (root / "gemini" / "extensions").is_dir()
    assert not (root / "gemini" / "marketplace.json").exists()

    claude = json.loads((root / "claude-code" / ".claude-plugin" / "marketplace.json").read_text())
    codex = json.loads((root / "codex" / ".agents" / "plugins" / "marketplace.json").read_text())
    assert claude["plugins"] == []
    assert codex["plugins"] == []
    assert codex["name"] == "Team-Marketplace"
    assert claude["owner"] == {"name": "Team Maintainer", "email": "team@example.local"}
    assert "owner" not in codex


def test_save_settings_dual_writes_metadata_and_preserves_package_entries(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata("Original Marketplace"))
    claude_path = root / "claude-code" / ".claude-plugin" / "marketplace.json"
    codex_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    claude = json.loads(claude_path.read_text())
    codex = json.loads(codex_path.read_text())
    claude["plugins"] = [{"name": "review-assistant", "source": "./plugins/review-assistant"}]
    codex["plugins"] = [{"name": "figma-context", "source": {"source": "local", "path": "./plugins/figma-context"}}]
    claude_path.write_text(json.dumps(claude), encoding="utf-8")
    codex_path.write_text(json.dumps(codex), encoding="utf-8")

    result = marketplace_service.save_settings("user-1", _metadata("Updated Marketplace"))

    assert result.error_code is None
    assert result.claude_written is True
    assert result.codex_written is True
    updated_claude = json.loads(claude_path.read_text())
    updated_codex = json.loads(codex_path.read_text())
    assert updated_claude["name"] == "Updated Marketplace"
    assert updated_claude["owner"]["name"] == "Team Maintainer"
    assert updated_claude["plugins"] == claude["plugins"]
    assert updated_codex["name"] == "Updated-Marketplace"
    assert "owner" not in updated_codex
    assert updated_codex["plugins"] == codex["plugins"]


def test_staged_codex_manifest_name_is_cli_safe(marketplace_service, monkeypatch, tmp_path):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata("本機市集"))
    package_path = root / "codex" / "plugins" / "figma-context"
    (package_path / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (package_path / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "figma-context", "version": "0.1.0"}),
        encoding="utf-8",
    )
    manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
    }]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(
        "app.services.marketplace_service.get_settings",
        lambda: SimpleNamespace(MANAGER_MARKETPLACE_INSTALL_DIR=str(tmp_path / "marketplace-install")),
    )

    runtime_package_path = marketplace_service._stage_install_provider_root("workspace-1", "codex", package_path)

    staged_manifest = json.loads((
        tmp_path / "marketplace-install" / "workspace_1" / "codex" / ".agents" / "plugins" / "marketplace.json"
    ).read_text(encoding="utf-8"))
    assert staged_manifest["name"] == "local-marketplace"
    assert runtime_package_path == Path("/marketplace-install/codex/plugins/figma-context")


def test_save_settings_reports_partial_success_when_second_adapter_fails(marketplace_service, monkeypatch):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata("Original Marketplace"))
    codex_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    original_write = marketplace_service._atomic_write_json

    def fail_codex_write(path, data):
        if path == codex_path:
            raise OSError("codex write failed")
        original_write(path, data)

    monkeypatch.setattr(marketplace_service, "_atomic_write_json", fail_codex_write)

    result = marketplace_service.save_settings("user-1", _metadata("Partially Saved Marketplace"))

    assert result.error_code == "marketplace.settings.partial_write"
    assert result.partial_success_provider == "claude-code"
    assert result.claude_written is True
    assert result.codex_written is False
    claude = json.loads((root / "claude-code" / ".claude-plugin" / "marketplace.json").read_text())
    codex = json.loads(codex_path.read_text())
    assert claude["name"] == "Partially Saved Marketplace"
    assert codex["name"] == "Original-Marketplace"


def test_resolve_package_path_rejects_invalid_package_ids(marketplace_service):
    marketplace_service.initialize_registry("user-1", _metadata())

    assert marketplace_service.resolve_package_path("user-1", "claude-code", "42crunch-api-security-testing").name == (
        "42crunch-api-security-testing"
    )
    assert marketplace_service.resolve_package_path("user-1", "claude-code", "wordpress.com").name == "wordpress.com"

    with pytest.raises(MarketplacePathError):
        marketplace_service.resolve_package_path("user-1", "codex", "../escape")

    with pytest.raises(MarketplacePathError):
        marketplace_service.resolve_package_path("user-1", "gemini", "bad/id")

    with pytest.raises(MarketplacePathError):
        marketplace_service.resolve_package_path("user-1", "claude-code", "bad..id")


def test_registry_scope_is_shared(marketplace_service):
    user_one_root = marketplace_service.get_registry_root("user-1")
    user_two_root = marketplace_service.get_registry_root("user-2")

    assert user_one_root == user_two_root
    assert str(user_one_root).endswith("marketplace/registry")
    assert "/users/" not in str(user_one_root)


def test_registry_scoped_records_are_shared_across_users(marketplace_service, monkeypatch):
    private_key_path = marketplace_service.get_registry_root("user-1") / ".marketplace" / "ssh" / "id_ed25519"
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_text("private-user-one", encoding="utf-8")
    marketplace_service.save_registry_ssh_key("user-1", {
        "publicKey": "ssh-ed25519 user-one",
        "privateKeyPath": str(private_key_path),
        "fingerprint": "SHA256:user-one",
    })
    marketplace_service.save_git_identity("user-1", {
        "name": "User One",
        "email": "user-one@example.local",
    })
    marketplace_service.record_activity(
        "user-1",
        action="import",
        status="success",
        provider="codex",
        package_id="figma-context",
    )
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002/",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(
                supports_user_scope=True,
                supports_marketplace_add=True,
            ),
        ),
    )
    marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert marketplace_service.get_registry_ssh_key("user-1")["fingerprint"] == "SHA256:user-one"
    assert marketplace_service.get_registry_ssh_key("user-2")["fingerprint"] == "SHA256:user-one"
    assert marketplace_service.get_git_identity("user-1") == {
        "name": "User One",
        "email": "user-one@example.local",
    }
    assert marketplace_service.get_git_identity("user-2") == {
        "name": "User One",
        "email": "user-one@example.local",
    }
    assert marketplace_service.list_packages("user-1").total == 1
    assert marketplace_service.list_packages("user-2").total == 1
    assert marketplace_service.list_activity("user-1").total == 2
    assert marketplace_service.list_activity("user-2").total == 2
    assert (marketplace_service.get_registry_root("user-1") / ".marketplace" / "install-intents.jsonl").exists()
    assert (marketplace_service.get_registry_root("user-2") / ".marketplace" / "install-intents.jsonl").exists()

    marketplace_service.validate_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="codex",
            source_kind="git",
            source="git@github.com:owner/repo.git",
        ),
    )
    marketplace_service.validate_import_source(
        "user-2",
        MarketplaceImportSource(
            provider="codex",
            source_kind="git",
            source="git@github.com:owner/repo.git",
        ),
    )


def test_get_settings_returns_uninitialized_before_bootstrap(marketplace_service):
    settings = marketplace_service.get_settings("user-1")
    root = marketplace_service.get_registry_root("user-1")

    assert settings.status == "uninitialized"
    assert settings.root_path == str(root)
    assert settings.display_name == ""
    assert settings.maintainer_name == ""
    assert settings.maintainer_email == ""
    assert not (root / "claude-code" / ".claude-plugin" / "marketplace.json").exists()
    assert not (root / "codex" / ".agents" / "plugins" / "marketplace.json").exists()


def test_registry_git_init_status_and_remote_are_shared(marketplace_service, tmp_path):
    remote_path = tmp_path / "registry.git"
    marketplace_service._run_process(["git", "init", "--bare", str(remote_path)], cwd=tmp_path)

    before = marketplace_service.get_registry_repository_status("user-1")
    initialized = marketplace_service.initialize_git_repository(
        "user-1",
        MarketplaceRegistryRemoteRequest(remoteUrl=str(remote_path)),
    )
    user_two = marketplace_service.get_registry_repository_status("user-2")

    assert before.is_git_repo is False
    assert before.can_init_safely is True
    assert initialized.success is True
    assert initialized.message_key == "marketplace.git.init_success"
    assert initialized.repository.is_git_repo is True
    assert initialized.repository.remote_url == str(remote_path)
    assert user_two.is_git_repo is True
    assert user_two.remote_url == str(remote_path)

    next_remote = tmp_path / "next.git"
    marketplace_service._run_process(["git", "init", "--bare", str(next_remote)], cwd=tmp_path)
    updated = marketplace_service.set_registry_remote(
        "user-1",
        MarketplaceRegistryRemoteRequest(remoteUrl=str(next_remote)),
    )

    assert updated.success is True
    assert updated.repository.remote_url == str(next_remote)


def test_registry_clone_bootstraps_missing_provider_manifests_and_refreshes_index(
    marketplace_service,
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source"
    source.mkdir()
    marketplace_service._run_process(["git", "init"], cwd=source)
    (source / "README.md").write_text("# Registry\n", encoding="utf-8")
    marketplace_service._run_process(["git", "add", "README.md"], cwd=source)
    marketplace_service._run_process(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Initial"],
        cwd=source,
    )
    remote = tmp_path / "remote.git"
    marketplace_service._run_process(["git", "clone", "--bare", str(source), str(remote)], cwd=tmp_path)

    empty = marketplace_service.list_packages("user-1")
    monkeypatch.setattr(marketplace_service, "_registry_fingerprint", lambda root: empty.registry_fingerprint)

    cloned = marketplace_service.clone_registry(
        "user-1",
        MarketplaceRegistryCloneRequest(remoteUrl=str(remote)),
    )
    root = marketplace_service.get_registry_root("user-1")

    assert cloned.success is True
    assert cloned.message_key == "marketplace.git.clone_success"
    assert cloned.repository.is_git_repo is True
    assert cloned.repository.remote_url == str(remote)
    assert (root / "README.md").read_text(encoding="utf-8") == "# Registry\n"
    assert (root / "claude-code" / ".claude-plugin" / "marketplace.json").exists()
    assert (root / "codex" / ".agents" / "plugins" / "marketplace.json").exists()
    assert marketplace_service.list_packages("user-1").total == 0


def test_registry_clone_preserves_existing_manifest_and_uses_it_to_bootstrap_missing_side(
    marketplace_service,
    tmp_path,
):
    source = tmp_path / "source"
    source.mkdir()
    marketplace_service._run_process(["git", "init"], cwd=source)
    claude_manifest = source / "claude-code" / ".claude-plugin" / "marketplace.json"
    claude_manifest.parent.mkdir(parents=True)
    claude_manifest.write_text(
        json.dumps({
            "name": "Remote Registry",
            "description": "Remote description",
            "owner": {"name": "Remote Maintainer", "email": "remote@example.local"},
            "plugins": [{"name": "remote-plugin", "source": "./plugins/remote-plugin"}],
        }),
        encoding="utf-8",
    )
    marketplace_service._run_process(["git", "add", "."], cwd=source)
    marketplace_service._run_process(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Remote registry"],
        cwd=source,
    )
    remote = tmp_path / "remote.git"
    marketplace_service._run_process(["git", "clone", "--bare", str(source), str(remote)], cwd=tmp_path)

    cloned = marketplace_service.clone_registry(
        "user-1",
        MarketplaceRegistryCloneRequest(remoteUrl=str(remote)),
    )
    root = marketplace_service.get_registry_root("user-1")
    cloned_claude = json.loads((root / "claude-code" / ".claude-plugin" / "marketplace.json").read_text())
    bootstrapped_codex = json.loads((root / "codex" / ".agents" / "plugins" / "marketplace.json").read_text())

    assert cloned.success is True
    assert cloned_claude["name"] == "Remote Registry"
    assert cloned_claude["owner"]["name"] == "Remote Maintainer"
    assert cloned_claude["plugins"] == [{"name": "remote-plugin", "source": "./plugins/remote-plugin"}]
    assert bootstrapped_codex["name"] == "Remote-Registry"
    assert bootstrapped_codex["description"] == "Remote description"
    assert bootstrapped_codex["plugins"] == []
    assert "owner" not in bootstrapped_codex


def test_registry_git_status_reports_provider_prefixed_staged_unstaged_and_untracked_files(marketplace_service):
    marketplace_service.initialize_git_repository("user-1")
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service._run_process(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "add", "."],
        cwd=root,
    )
    marketplace_service._run_process(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Initial registry"],
        cwd=root,
    )

    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({
            "name": "Changed Registry",
            "description": "Changed",
            "plugins": [],
        }),
        encoding="utf-8",
    )
    claude_readme = root / "claude-code" / "plugins" / "review-assistant" / "README.md"
    claude_readme.parent.mkdir(parents=True)
    claude_readme.write_text("# Review\n", encoding="utf-8")
    gemini_manifest = root / "gemini" / "extensions" / "workspace-tools" / "gemini-extension.json"
    gemini_manifest.parent.mkdir(parents=True)
    gemini_manifest.write_text(json.dumps({"name": "workspace-tools"}), encoding="utf-8")
    marketplace_service._run_process(["git", "add", "gemini/extensions/workspace-tools/gemini-extension.json"], cwd=root)

    status = marketplace_service.get_registry_git_status("user-1")

    assert status.is_git_repo is True
    assert status.branch
    assert [item.path for item in status.staged] == ["gemini/extensions/workspace-tools/gemini-extension.json"]
    assert [item.path for item in status.unstaged] == ["codex/.agents/plugins/marketplace.json"]
    assert [item.path for item in status.untracked] == ["claude-code/plugins/review-assistant/README.md"]
    assert status.staged_count == 1
    assert status.unstaged_count == 1
    assert status.untracked_count == 1


def test_registry_git_status_initializes_existing_registry_content(marketplace_service):
    marketplace_service.initialize_registry("user-1", _metadata())
    root = marketplace_service.get_registry_root("user-1")
    package_readme = root / "claude-code" / "plugins" / "settings" / "README.md"
    package_readme.parent.mkdir(parents=True)
    package_readme.write_text("# Settings\n", encoding="utf-8")

    status = marketplace_service.get_registry_git_status("user-1")

    assert status.is_git_repo is True
    assert (root / ".git").is_dir()
    assert status.staged == []
    assert status.unstaged == []
    assert {item.path for item in status.untracked} >= {
        "claude-code/.claude-plugin/marketplace.json",
        "codex/.agents/plugins/marketplace.json",
        "claude-code/plugins/settings/README.md",
    }


def test_registry_file_diff_supports_worktree_index_commit_and_untracked_files(marketplace_service):
    marketplace_service.initialize_git_repository("user-1")
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service._run_process(["git", "add", "."], cwd=root)
    marketplace_service._run_process(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Initial registry"],
        cwd=root,
    )
    first_commit = marketplace_service._git_output(root, ["rev-parse", "HEAD"])

    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({"name": "Changed Registry", "description": "Changed", "plugins": []}, indent=2),
        encoding="utf-8",
    )
    worktree_diff = marketplace_service.get_registry_file_diff(
        "user-1",
        "codex/.agents/plugins/marketplace.json",
    )
    marketplace_service._run_process(["git", "add", "codex/.agents/plugins/marketplace.json"], cwd=root)
    index_diff = marketplace_service.get_registry_file_diff(
        "user-1",
        "codex/.agents/plugins/marketplace.json",
        head="INDEX",
    )
    marketplace_service._run_process(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Update codex registry"],
        cwd=root,
    )
    second_commit = marketplace_service._git_output(root, ["rev-parse", "HEAD"])
    commit_diff = marketplace_service.get_registry_commit_file_diff(
        "user-1",
        second_commit,
        "codex/.agents/plugins/marketplace.json",
    )
    commit_files = marketplace_service.get_registry_commit_files("user-1", second_commit)
    readme = root / "claude-code" / "plugins" / "review-assistant" / "README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text("# Review\n", encoding="utf-8")
    untracked_diff = marketplace_service.get_registry_file_diff(
        "user-1",
        "claude-code/plugins/review-assistant/README.md",
    )

    assert first_commit
    assert worktree_diff.head == "WORKTREE"
    assert "+  \"name\": \"Changed Registry\"" in worktree_diff.patch
    assert index_diff.head == "INDEX"
    assert "+  \"name\": \"Changed Registry\"" in index_diff.patch
    assert commit_diff.commit_id == second_commit
    assert "+  \"name\": \"Changed Registry\"" in commit_diff.patch
    assert [item.path for item in commit_files.files] == ["codex/.agents/plugins/marketplace.json"]
    assert untracked_diff.patch.startswith("--- /dev/null")
    assert "+# Review" in untracked_diff.patch


def test_registry_file_diff_rejects_paths_outside_registry(marketplace_service):
    marketplace_service.initialize_git_repository("user-1")

    with pytest.raises(MarketplacePathError):
        marketplace_service.get_registry_file_diff("user-1", "../outside.json")


def test_registry_stage_unstage_commit_and_history_prevent_empty_commits(marketplace_service):
    marketplace_service.initialize_git_repository("user-1")
    root = marketplace_service.get_registry_root("user-1")
    empty_commit = marketplace_service.commit_registry_changes(
        "user-1",
        MarketplaceGitCommitRequest(message="Nothing"),
    )
    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({"name": "Changed Registry", "description": "Changed", "plugins": []}, indent=2),
        encoding="utf-8",
    )

    staged = marketplace_service.stage_registry_paths(
        "user-1",
        MarketplaceGitPathRequest(paths=["codex/.agents/plugins/marketplace.json"]),
    )
    unstaged = marketplace_service.unstage_registry_paths(
        "user-1",
        MarketplaceGitPathRequest(paths=["codex/.agents/plugins/marketplace.json"]),
    )
    committed = marketplace_service.commit_registry_changes(
        "user-1",
        MarketplaceGitCommitRequest(message="Update codex registry", paths=["codex/.agents/plugins/marketplace.json"]),
    )
    history = marketplace_service.list_registry_commits("user-1")

    assert empty_commit.success is False
    assert empty_commit.error_code == "marketplace.git.no_changes_to_commit"
    assert [item.path for item in staged.staged] == ["codex/.agents/plugins/marketplace.json"]
    assert staged.unstaged == []
    assert staged.staged_count == 1
    assert "codex/.agents/plugins/marketplace.json" in [item.path for item in unstaged.untracked]
    assert unstaged.staged_count == 0
    assert committed.success is True
    assert committed.message_key == "marketplace.git.commit_success"
    assert committed.commit is not None
    assert committed.commit.message == "Update codex registry"
    assert history.total == 1
    assert history.items[0].id == committed.commit.id
    assert history.items[0].files_changed == 1


def test_registry_fetch_pull_and_push_sync_with_remote(marketplace_service, tmp_path):
    remote = tmp_path / "registry.git"
    marketplace_service._run_process(["git", "init", "--bare", str(remote)], cwd=tmp_path)
    marketplace_service.initialize_git_repository(
        "user-1",
        MarketplaceRegistryRemoteRequest(remoteUrl=str(remote)),
    )
    root = marketplace_service.get_registry_root("user-1")
    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({"name": "Changed Registry", "description": "Changed", "plugins": []}, indent=2),
        encoding="utf-8",
    )
    commit = marketplace_service.commit_registry_changes(
        "user-1",
        MarketplaceGitCommitRequest(message="Initial registry", paths=["codex/.agents/plugins/marketplace.json"]),
    )
    push = marketplace_service.push_registry("user-1")
    peer = tmp_path / "peer"
    marketplace_service._run_process(["git", "clone", str(remote), str(peer)], cwd=tmp_path)
    (peer / "REMOTE.md").write_text("# Remote\n", encoding="utf-8")
    marketplace_service._run_process(["git", "add", "REMOTE.md"], cwd=peer)
    marketplace_service._run_process(
        ["git", "-c", "user.name=Peer", "-c", "user.email=peer@example.local", "commit", "-m", "Remote update"],
        cwd=peer,
    )
    marketplace_service._run_process(["git", "push", "origin", "HEAD"], cwd=peer)

    fetch = marketplace_service.fetch_registry("user-1")
    pull = marketplace_service.pull_registry("user-1")

    assert commit.success is True
    assert push.success is True
    assert push.message_key == "marketplace.git.push_success"
    assert fetch.success is True
    assert fetch.message_key == "marketplace.git.fetch_success"
    assert pull.success is True
    assert pull.message_key == "marketplace.git.pull_success"
    assert (root / "REMOTE.md").read_text(encoding="utf-8") == "# Remote\n"


def test_registry_ssh_key_generation_stores_private_key_and_returns_public_metadata(marketplace_service):
    missing = marketplace_service.get_registry_ssh_key_metadata("user-1")
    generated = marketplace_service.generate_registry_ssh_key("user-1")
    loaded = marketplace_service.get_registry_ssh_key_metadata("user-1")
    record = marketplace_service.get_registry_ssh_key("user-1")

    assert missing.exists is False
    assert generated.exists is True
    assert generated.algorithm == "ed25519"
    assert generated.public_key is not None
    assert generated.public_key.startswith("ssh-ed25519 ")
    assert generated.fingerprint is not None
    assert generated.fingerprint.startswith("SHA256:")
    assert generated.created_at
    assert loaded == generated
    assert record is not None
    assert "privateKey" not in record
    assert Path(record["privateKeyPath"]).exists()
    assert Path(record["publicKeyPath"]).exists()


def test_list_packages_scans_provider_native_registry_entries(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    claude_manifest_path = root / "claude-code" / ".claude-plugin" / "marketplace.json"
    claude_manifest = json.loads(claude_manifest_path.read_text())
    claude_manifest["plugins"] = [{
        "name": "review-assistant",
        "source": "./plugins/review-assistant",
        "description": "Review workflow package",
        "category": "quality",
        "tags": ["review"],
    }]
    claude_manifest_path.write_text(json.dumps(claude_manifest), encoding="utf-8")
    package_root = root / "claude-code" / "plugins" / "review-assistant"
    (package_root / ".claude-plugin").mkdir(parents=True)
    (package_root / "skills").mkdir()
    (package_root / "README.md").write_text("# Review Assistant\n", encoding="utf-8")
    (package_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "review-assistant", "version": "1.2.3"}),
        encoding="utf-8",
    )

    result = marketplace_service.list_packages("user-1", provider="claude-code", features=["skills"])

    assert result.total == 1
    summary = result.items[0]
    assert summary.provider == "claude-code"
    assert summary.package_id == "review-assistant"
    assert summary.package_type == "plugin"
    assert summary.display_name == "review-assistant"
    assert summary.version == "1.2.3"
    assert summary.category == "quality"
    assert summary.validation_severity == "none"
    assert "skills" in summary.indexed_resource_names


def test_list_packages_applies_query_category_feature_filters_and_returns_facets(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    claude_manifest_path = root / "claude-code" / ".claude-plugin" / "marketplace.json"
    codex_manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    claude_manifest = json.loads(claude_manifest_path.read_text())
    codex_manifest = json.loads(codex_manifest_path.read_text())
    claude_manifest["plugins"] = [{
        "name": "review-assistant",
        "source": "./plugins/review-assistant",
        "description": "Review workflow package",
        "category": "quality",
        "tags": ["review", "skills"],
    }]
    codex_manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
        "description": "Figma MCP package",
        "category": "design",
        "tags": ["mcp", "commands"],
    }]
    claude_manifest_path.write_text(json.dumps(claude_manifest), encoding="utf-8")
    codex_manifest_path.write_text(json.dumps(codex_manifest), encoding="utf-8")
    claude_package = root / "claude-code" / "plugins" / "review-assistant"
    codex_package = root / "codex" / "plugins" / "figma-context"
    (claude_package / ".claude-plugin").mkdir(parents=True)
    (codex_package / ".codex-plugin").mkdir(parents=True)
    (claude_package / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "review-assistant", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (codex_package / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "figma-context", "version": "1.0.0", "description": "Figma MCP package"}),
        encoding="utf-8",
    )

    all_packages = marketplace_service.list_packages("user-1", page_size=1)
    design_packages = marketplace_service.list_packages("user-1", category="design")
    command_packages = marketplace_service.list_packages("user-1", features=["commands"])
    review_packages = marketplace_service.list_packages("user-1", q="review", provider="claude-code")
    missing_packages = marketplace_service.list_packages("user-1", q="not-found")

    assert all_packages.total == 2
    assert all_packages.page_size == 1
    assert all_packages.total_pages == 2
    assert all_packages.categories == ["design", "quality"]
    assert all_packages.source_types == ["created"]
    assert all_packages.validation_severities == ["none"]
    assert [item.package_id for item in design_packages.items] == ["figma-context"]
    assert [item.package_id for item in command_packages.items] == ["figma-context"]
    assert [item.package_id for item in review_packages.items] == ["review-assistant"]
    assert missing_packages.total == 0


def test_codex_scan_does_not_read_claude_marketplace_manifest(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    claude_manifest_path = root / "claude-code" / ".claude-plugin" / "marketplace.json"
    claude_manifest = json.loads(claude_manifest_path.read_text())
    claude_manifest["plugins"] = [{
        "name": "claude-only",
        "source": "./plugins/claude-only",
    }]
    claude_manifest_path.write_text(json.dumps(claude_manifest), encoding="utf-8")
    package_root = root / "claude-code" / "plugins" / "claude-only"
    (package_root / ".claude-plugin").mkdir(parents=True)
    (package_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "claude-only"}),
        encoding="utf-8",
    )

    codex_result = marketplace_service.list_packages("user-1", provider="codex")

    assert codex_result.total == 0


def test_get_package_detail_returns_manifest_and_readme(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    codex_manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest = json.loads(codex_manifest_path.read_text())
    codex_manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
        "category": "design",
    }]
    codex_manifest_path.write_text(json.dumps(codex_manifest), encoding="utf-8")
    package_root = root / "codex" / "plugins" / "figma-context"
    (package_root / ".codex-plugin").mkdir(parents=True)
    (package_root / "README.md").write_text("# Figma Context\n", encoding="utf-8")
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "figma-context", "version": "0.2.0", "description": "Figma MCP package"}),
        encoding="utf-8",
    )

    detail = marketplace_service.get_package_detail("user-1", "codex", "figma-context")

    assert detail is not None
    assert detail.provider == "codex"
    assert detail.manifest_metadata["version"] == "0.2.0"
    assert detail.readme_markdown == "# Figma Context\n"
    assert detail.catalog_metadata["category"] == "design"
    assert detail.feature_content.commands == []
    assert [item.path for item in detail.package_files] == [
        ".codex-plugin/plugin.json",
        "README.md",
    ]
    assert detail.package_files[1].content == "# Figma Context\n"


def test_get_package_detail_returns_binary_package_files_as_base64(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    codex_manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest = json.loads(codex_manifest_path.read_text())
    codex_manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
    }]
    codex_manifest_path.write_text(json.dumps(codex_manifest), encoding="utf-8")
    package_root = root / "codex" / "plugins" / "figma-context"
    (package_root / ".codex-plugin").mkdir(parents=True)
    (package_root / "assets").mkdir()
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "figma-context"}),
        encoding="utf-8",
    )
    raw_image = b"\x89PNG\r\n\x1a\n\x00"
    (package_root / "assets" / "logo.png").write_bytes(raw_image)

    detail = marketplace_service.get_package_detail("user-1", "codex", "figma-context")

    assert detail is not None
    image_file = next(item for item in detail.package_files if item.path == "assets/logo.png")
    assert image_file.binary is True
    assert image_file.mime_type == "image/png"
    assert image_file.content == base64.b64encode(raw_image).decode("ascii")


def test_get_package_detail_returns_feature_content(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    claude_manifest_path = root / "claude-code" / ".claude-plugin" / "marketplace.json"
    claude_manifest = json.loads(claude_manifest_path.read_text())
    claude_manifest["plugins"] = [{
        "name": "discord",
        "source": "./plugins/discord",
        "category": "productivity",
    }]
    claude_manifest_path.write_text(json.dumps(claude_manifest), encoding="utf-8")
    package_root = root / "claude-code" / "plugins" / "discord"
    (package_root / ".claude-plugin").mkdir(parents=True)
    (package_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "discord", "version": "0.0.4"}),
        encoding="utf-8",
    )
    (package_root / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"discord": {"command": "bun", "args": ["run", "start"]}}}),
        encoding="utf-8",
    )
    (package_root / "skills" / "access").mkdir(parents=True)
    (package_root / "skills" / "access" / "SKILL.md").write_text(
        "# Access\n\ndescription: Manage Discord access",
        encoding="utf-8",
    )

    detail = marketplace_service.get_package_detail("user-1", "claude-code", "discord")

    assert detail is not None
    assert detail.feature_content.mcp_servers[0].name == "discord"
    assert detail.feature_content.mcp_servers[0].data["command"] == "bun"
    assert detail.feature_content.skills[0].path == "skills/access/SKILL.md"
    assert "# Access" in detail.feature_content.skills[0].content
    assert [item.path for item in detail.package_files] == [
        ".claude-plugin/plugin.json",
        ".mcp.json",
        "skills/access/SKILL.md",
    ]
    assert '"mcpServers"' in detail.package_files[1].content


def test_get_package_detail_discovers_and_sanitizes_readme_markdown(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    claude_manifest_path = root / "claude-code" / ".claude-plugin" / "marketplace.json"
    claude_manifest = json.loads(claude_manifest_path.read_text())
    claude_manifest["plugins"] = [{
        "name": "review-assistant",
        "source": "./plugins/review-assistant",
    }]
    claude_manifest_path.write_text(json.dumps(claude_manifest), encoding="utf-8")
    package_root = root / "claude-code" / "plugins" / "review-assistant"
    (package_root / ".claude-plugin").mkdir(parents=True)
    (package_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "review-assistant"}),
        encoding="utf-8",
    )
    (package_root / "readme.md").write_text(
        "\n".join([
            "# Review Assistant",
            "<script>alert('x')</script>",
            "<iframe src=\"https://example.invalid\"></iframe>",
            "<img src=\"x\" onerror=\"alert('x')\">",
            "[Unsafe](javascript:alert('x'))",
            "[External](https://example.com)",
        ]),
        encoding="utf-8",
    )

    detail = marketplace_service.get_package_detail("user-1", "claude-code", "review-assistant")

    assert detail is not None
    assert "# Review Assistant" in detail.readme_markdown
    assert "script" not in detail.readme_markdown.lower()
    assert "iframe" not in detail.readme_markdown.lower()
    assert "onerror" not in detail.readme_markdown.lower()
    assert "javascript:" not in detail.readme_markdown.lower()
    assert "[Unsafe](#)" in detail.readme_markdown
    assert "[External](https://example.com)" in detail.readme_markdown


def test_get_package_detail_exposes_catalog_and_manifest_metadata_conflict(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    codex_manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest = json.loads(codex_manifest_path.read_text())
    codex_manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
        "displayName": "Catalog Name",
        "description": "Catalog description",
        "version": "1.0.0",
        "category": "design",
        "tags": ["catalog"],
    }]
    codex_manifest_path.write_text(json.dumps(codex_manifest), encoding="utf-8")
    package_root = root / "codex" / "plugins" / "figma-context"
    (package_root / ".codex-plugin").mkdir(parents=True)
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({
            "name": "figma-context",
            "displayName": "Manifest Name",
            "version": "0.1.0",
            "description": "Manifest description",
            "keywords": ["manifest"],
        }),
        encoding="utf-8",
    )

    list_result = marketplace_service.list_packages("user-1", provider="codex")
    detail = marketplace_service.get_package_detail("user-1", "codex", "figma-context")

    assert list_result.items[0].display_name == "Catalog Name"
    assert list_result.items[0].validation_severity == "warning"
    assert detail is not None
    assert detail.metadata_conflict is True
    assert detail.catalog_metadata["description"] == "Catalog description"
    assert detail.manifest_metadata["description"] == "Manifest description"
    assert detail.validation_results[0].code == "marketplace.validation.metadata_conflict"
    assert detail.validation_results[0].severity == "warning"


def test_list_packages_tolerates_missing_provider_manifest(marketplace_service):
    """Marketplace listings can carry full plugin metadata directly, so a
    package directory without plugin.json must still surface in listings
    without an error severity (e.g. csharp-lsp from claude-plugins-official)."""
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plugins"] = [{
        "name": "listing-only-plugin",
        "source": {"source": "local", "path": "./plugins/listing-only-plugin"},
        "description": "Listing-only plugin",
        "version": "1.0.0",
    }]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (root / "codex" / "plugins" / "listing-only-plugin").mkdir(parents=True)

    result = marketplace_service.list_packages("user-1")

    assert result.total == 1
    assert result.items[0].validation_severity == "none"


def test_package_index_refreshes_when_registry_fingerprint_changes(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    first = marketplace_service.list_packages("user-1")
    assert first.total == 0

    manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
    }]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    package_root = root / "codex" / "plugins" / "figma-context"
    (package_root / ".codex-plugin").mkdir(parents=True)
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "figma-context", "version": "0.1.0"}),
        encoding="utf-8",
    )

    refreshed = marketplace_service.list_packages("user-1")

    assert refreshed.total == 1
    assert refreshed.registry_fingerprint != first.registry_fingerprint


def test_explicit_package_index_refresh_invalidates_cached_entries(marketplace_service, monkeypatch):
    marketplace_service.initialize_registry("user-1", _metadata())
    first = marketplace_service.list_packages("user-1")
    assert first.total == 0

    monkeypatch.setattr(marketplace_service, "_registry_fingerprint", lambda root: first.registry_fingerprint)
    stale = marketplace_service.list_packages("user-1")
    assert stale.total == 0

    monkeypatch.setattr(marketplace_service, "_scan_registry", lambda root: [
        MarketplacePackageSummary(
            provider="codex",
            package_type="plugin",
            package_id="not-a-summary",
            display_name="Not A Summary",
            source_type="created",
            registry_path="codex/plugins/not-a-summary",
            revision="rev-1",
            updated_at="2026-05-07T00:00:00Z",
        )
    ])

    refreshed = marketplace_service.refresh_package_index("user-1")

    assert refreshed.total == 1
    assert refreshed.items[0].package_id == "not-a-summary"


def test_package_index_invalidates_after_registry_mutations(marketplace_service, monkeypatch):
    marketplace_service.initialize_registry("user-1", _metadata())
    empty = marketplace_service.list_packages("user-1")
    monkeypatch.setattr(marketplace_service, "_registry_fingerprint", lambda root: empty.registry_fingerprint)

    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    after_create = marketplace_service.list_packages("user-1")
    assert [item.package_id for item in after_create.items] == ["figma-context"]

    saved = marketplace_service.save_package(
        "user-1",
        MarketplacePackageSaveRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            manifest={
                "name": "figma-context",
                "version": "0.9.0",
                "description": "Updated package",
            },
        ),
    )
    after_save = marketplace_service.list_packages("user-1")
    assert after_save.items[0].version == "0.9.0"

    marketplace_service.delete_package(
        "user-1",
        MarketplacePackageDeleteRequest(
            provider="codex",
            package_id="figma-context",
            revision=saved.revision,
        ),
    )
    assert marketplace_service.list_packages("user-1").total == 0

    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-index-refresh"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "imported-context",
                "source": {"source": "local", "path": "./plugins/imported-context"},
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "imported-context"
    (package_path / ".codex-plugin").mkdir(parents=True)
    (package_path / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({
            "name": "imported-context",
            "version": "1.0.0",
            "description": "Imported package",
        }),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(
        provider="codex",
        sourceKind="local",
        source=str(source_root),
    )
    candidates = marketplace_service.scan_import_source("user-1", source)

    marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )

    after_import = marketplace_service.list_packages("user-1")
    assert [item.package_id for item in after_import.items] == ["imported-context"]
    assert after_import.items[0].source_type == "imported"


def test_create_package_writes_provider_native_scaffold_and_marketplace_entry(marketplace_service):
    detail = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    root = marketplace_service.get_registry_root("user-1")
    manifest = json.loads((root / "codex" / ".agents" / "plugins" / "marketplace.json").read_text())

    assert detail.provider == "codex"
    assert detail.package_id == "figma-context"
    assert detail.manifest_metadata["version"] == "0.1.0"
    assert manifest["plugins"] == [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
        "description": "Figma MCP package",
        "category": "uncategorized",
    }]
    assert (root / "codex" / "plugins" / "figma-context" / "README.md").exists()


def test_save_package_checks_revision_patches_current_entry_and_strips_root_metadata(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="claude-code",
            package_id="review-assistant",
            display_name="Review Assistant",
            description="Review package",
        ),
    )
    result = marketplace_service.save_package(
        "user-1",
        MarketplacePackageSaveRequest(
            provider="claude-code",
            package_id="review-assistant",
            revision=created.revision,
            listing={
                "name": "review-assistant",
                "source": "./plugins/review-assistant",
                "owner": {"name": "Should Strip"},
                "description": "Should Strip",
            },
            manifest={"name": "review-assistant"},
            readme_markdown="# Updated Review Assistant\n",
        ),
    )
    root = marketplace_service.get_registry_root("user-1")
    manifest = json.loads((root / "claude-code" / ".claude-plugin" / "marketplace.json").read_text())

    assert result.revision != created.revision
    assert result.validation_results[0].code == "marketplace.validation.root_metadata_stripped"
    assert manifest["plugins"] == [{"name": "review-assistant", "source": "./plugins/review-assistant"}]
    assert manifest["owner"]["name"] == "Marketplace Maintainer"
    readme_path = root / "claude-code" / "plugins" / "review-assistant" / "README.md"
    assert readme_path.read_text() == "# Updated Review Assistant\n"


def test_save_package_blocks_provider_manifest_validation_errors_before_write(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    root = marketplace_service.get_registry_root("user-1")
    manifest_path = root / "codex" / "plugins" / "figma-context" / ".codex-plugin" / "plugin.json"
    original_manifest = json.loads(manifest_path.read_text())

    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_service.save_package(
            "user-1",
            MarketplacePackageSaveRequest(
                provider="codex",
                package_id="figma-context",
                revision=created.revision,
                manifest={
                    "name": "wrong-id",
                    "version": "0.2.0",
                },
            ),
        )

    assert [result["code"] for result in exc_info.value.results] == [
        "marketplace.validation.invalid_manifest_shape",
        "marketplace.validation.package_identity_mismatch",
    ]
    assert json.loads(manifest_path.read_text()) == original_manifest


def test_save_package_rejects_listing_projection_for_different_package(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="claude-code",
            package_id="review-assistant",
            display_name="Review Assistant",
            description="Review package",
        ),
    )
    root = marketplace_service.get_registry_root("user-1")
    manifest_path = root / "claude-code" / ".claude-plugin" / "marketplace.json"
    original_manifest = json.loads(manifest_path.read_text())

    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_service.save_package(
            "user-1",
            MarketplacePackageSaveRequest(
                provider="claude-code",
                package_id="review-assistant",
                revision=created.revision,
                listing={
                    "name": "wrong-id",
                    "source": "./plugins/review-assistant",
                },
            ),
        )

    assert exc_info.value.results[0]["code"] == "marketplace.validation.package_identity_mismatch"
    assert json.loads(manifest_path.read_text()) == original_manifest


def test_validation_taxonomy_blocks_only_error_results_for_mutating_actions(marketplace_service):
    results = [
        {
            "severity": "info",
            "code": "marketplace.validation.root_metadata_stripped",
            "messageKey": "marketplace.validation.root_metadata_stripped",
        },
        {
            "severity": "warning",
            "code": "marketplace.validation.metadata_conflict",
            "messageKey": "marketplace.validation.metadata_conflict",
        },
        {
            "severity": "error",
            "code": "marketplace.validation.invalid_manifest_shape",
            "messageKey": "marketplace.validation.invalid_manifest_shape",
        },
    ]

    assert marketplace_service.validation_blocks_action(results[:2], "save") is False
    assert marketplace_service.validation_blocks_action(results[:2], "export") is False
    assert marketplace_service.validation_blocks_action(results[:2], "install") is False
    assert marketplace_service.validation_blocks_action(results[:2], "importCopy") is False
    assert marketplace_service.validation_blocks_action(results, "save") is True
    assert marketplace_service.validation_blocks_action(results, "export") is True
    assert marketplace_service.validation_blocks_action(results, "install") is True
    assert marketplace_service.validation_blocks_action(results, "importCopy") is True
    assert marketplace_service.blocking_validation_results(results, "save") == [results[2]]


def test_export_package_blocks_error_validation_but_allows_warning_validation(marketplace_service):
    root = marketplace_service.get_registry_root("user-1")
    marketplace_service.initialize_registry("user-1", _metadata())
    manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
        "description": "Catalog description",
    }]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    package_root = root / "codex" / "plugins" / "figma-context"
    (package_root / ".codex-plugin").mkdir(parents=True)
    plugin_manifest_path = package_root / ".codex-plugin" / "plugin.json"
    plugin_manifest_path.write_text(
        json.dumps({
            "name": "figma-context",
            "version": "0.1.0",
            "description": "Manifest description",
        }),
        encoding="utf-8",
    )

    detail = marketplace_service.get_package_detail("user-1", "codex", "figma-context")
    warning_archive = marketplace_service.export_package("user-1", "codex", "figma-context", detail.revision)
    # Corrupt the manifest with invalid JSON to trigger an error-level
    # validation result. Missing manifest no longer blocks export because
    # marketplace listings may declare the metadata in lieu of plugin.json.
    plugin_manifest_path.write_text("{not valid json", encoding="utf-8")
    broken_detail = marketplace_service.get_package_detail("user-1", "codex", "figma-context")

    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_service.export_package("user-1", "codex", "figma-context", broken_detail.revision)

    assert warning_archive
    assert exc_info.value.results[0]["code"] == "marketplace.validation.invalid_manifest_shape"


def test_delete_package_checks_revision_and_removes_marketplace_entry(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    stale = marketplace_service.delete_package(
        "user-1",
        MarketplacePackageDeleteRequest(
            provider="codex",
            package_id="figma-context",
            revision="stale",
        ),
    )
    deleted = marketplace_service.delete_package(
        "user-1",
        MarketplacePackageDeleteRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
        ),
    )
    root = marketplace_service.get_registry_root("user-1")
    manifest = json.loads((root / "codex" / ".agents" / "plugins" / "marketplace.json").read_text())

    assert stale.deleted is False
    assert stale.error_code == "marketplace.package.revision_conflict"
    assert deleted.deleted is True
    assert not (root / "codex" / "plugins" / "figma-context").exists()
    assert manifest["plugins"] == []
    activity = marketplace_service.list_activity("user-1")
    assert activity.total == 2
    assert [record.action for record in activity.items] == ["delete", "delete"]
    assert activity.items[0].status == "success"
    assert activity.items[0].provider == "codex"
    assert activity.items[0].package_id == "figma-context"
    assert activity.items[1].status == "failed"
    assert activity.items[1].error_code == "marketplace.package.revision_conflict"


def test_record_activity_supports_import_and_install_actions(marketplace_service):
    imported = marketplace_service.record_activity(
        "user-1",
        action="import",
        status="success",
        provider="claude-code",
        package_id="review-assistant",
    )
    installed = marketplace_service.record_activity(
        "user-1",
        action="install",
        status="failed",
        provider="codex",
        package_id="figma-context",
        error_code="marketplace.install.cliUnavailable",
    )

    activity = marketplace_service.list_activity("user-1")

    assert imported.id
    assert installed.id
    assert activity.total == 2
    assert [record.action for record in activity.items] == ["install", "import"]
    assert activity.items[0].error_code == "marketplace.install.cliUnavailable"


def test_detect_cli_reports_missing_executable(marketplace_service, monkeypatch):
    monkeypatch.setattr("app.services.marketplace_service.shutil.which", lambda name: None)

    preflight = marketplace_service.detect_cli("codex")

    assert preflight.available is False
    assert preflight.error_code == "marketplace.install.cli_unavailable"
    assert preflight.executable_path is None


def test_detect_cli_reports_version_and_capabilities(marketplace_service, monkeypatch):
    monkeypatch.setattr("app.services.marketplace_service.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="codex 1.2.3", stderr="")
        return SimpleNamespace(returncode=0, stdout="codex marketplace add --user", stderr="")

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    preflight = marketplace_service.detect_cli("codex")

    assert preflight.available is True
    assert preflight.executable_path == "/usr/bin/codex"
    assert preflight.version == "1.2.3"
    assert preflight.error_code is None
    assert preflight.capabilities.supports_marketplace_add is True
    assert preflight.capabilities.supports_user_scope is True


def test_detect_cli_reports_unsupported_version(marketplace_service, monkeypatch):
    monkeypatch.setattr("app.services.marketplace_service.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        marketplace_service,
        "_cli_preflight_config",
        lambda provider: {
            "executables": ["codex"],
            "versionArgs": ["--version"],
            "helpArgs": ["--help"],
            "minimumVersion": "2.0.0",
        },
    )

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="codex 1.2.3", stderr="")

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    preflight = marketplace_service.detect_cli("codex")

    assert preflight.available is True
    assert preflight.version == "1.2.3"
    assert preflight.error_code == "marketplace.install.cli_version_unsupported"


def test_detect_cli_reports_missing_required_capability(marketplace_service, monkeypatch):
    monkeypatch.setattr("app.services.marketplace_service.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="gemini 0.9.0", stderr="")
        return SimpleNamespace(returncode=0, stdout="gemini help", stderr="")

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    preflight = marketplace_service.detect_cli("gemini")

    assert preflight.available is True
    assert preflight.error_code == "marketplace.install.cli_capability_missing"
    assert preflight.capabilities.supports_extension_install is False


def test_install_package_returns_cli_unavailable_from_preflight(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=False,
            error_code="marketplace.install.cli_unavailable",
        ),
    )

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=marketplace_service.get_package_detail("user-1", "codex", "figma-context").revision,
            workspace_id="workspace-1",
        ),
    )
    activity = marketplace_service.list_activity("user-1")

    assert result.status == "cliUnavailable"
    assert result.error_code == "marketplace.install.cli_unavailable"
    assert activity.items[0].action == "install"
    assert activity.items[0].error_code == "marketplace.install.cli_unavailable"


def test_install_package_returns_cli_version_unsupported_from_preflight(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_marketplace_add=True),
            error_code="marketplace.install.cli_version_unsupported",
        ),
    )

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert result.status == "cliVersionUnsupported"
    assert result.error_code == "marketplace.install.cli_version_unsupported"


def test_install_package_does_not_build_command_when_preflight_fails(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    adapter = marketplace_service._get_adapter("codex")
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            error_code="marketplace.install.cli_capability_missing",
        ),
    )

    def fail_build_command(package_path, workspace_id, preflight):
        raise AssertionError("build_install_command should not run after failed preflight")

    monkeypatch.setattr(adapter, "build_install_command", fail_build_command)

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert result.status == "cliCapabilityMissing"
    assert result.error_code == "marketplace.install.cli_capability_missing"


def test_install_package_returns_validation_failure_before_runtime_resolution(marketplace_service, monkeypatch):
    marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    package_path = marketplace_service.resolve_package_path("user-1", "codex", "figma-context")
    (package_path / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "wrong-id"}),
        encoding="utf-8",
    )

    def fail_runtime_resolution(workspace_id):
        raise AssertionError("runtime resolution should not run when validation blocks install")

    monkeypatch.setattr(marketplace_service, "_resolve_install_runtime", fail_runtime_resolution)

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=marketplace_service.get_package_detail("user-1", "codex", "figma-context").revision,
            workspace_id="workspace-1",
        ),
    )

    assert result.status == "validation"
    assert result.error_code == "marketplace.install.validation_failed"
    activity = marketplace_service.list_activity("user-1")
    assert activity.items[0].action == "install"
    assert activity.items[0].status == "failed"


def test_install_package_returns_runtime_delegation_unavailable_after_command_plan_validation(
    marketplace_service,
    monkeypatch,
):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002/",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(
                supports_user_scope=True,
                supports_marketplace_add=True,
            ),
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_execute_install_command_on_runtime",
        lambda request, command_plan, *, runtime_url: marketplace_service._install_result(
            request,
            "runtimeUnavailable",
            "marketplace.install.runtime_delegation_unavailable",
        ),
    )

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert result.status == "runtimeUnavailable"
    assert result.error_code == "marketplace.install.runtime_delegation_unavailable"
    intents_path = marketplace_service.get_registry_root("user-1") / ".marketplace" / "install-intents.jsonl"
    intent = json.loads(intents_path.read_text(encoding="utf-8").splitlines()[0])
    assert intent["runtimeUrl"] == "http://workspace-runtime:3002/"
    activity = marketplace_service.list_activity("user-1")
    assert activity.items[0].action == "install"
    assert activity.items[0].status == "failed"


def test_install_package_delegates_command_plan_to_workspace_runtime(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002/",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(
                supports_user_scope=True,
                supports_marketplace_add=True,
            ),
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "detect_cli",
        lambda provider: (_ for _ in ()).throw(AssertionError("install should use runtime CLI detection")),
    )
    captured: dict[str, object] = {}

    class RuntimeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "success",
                "exitCode": 0,
                "startedAt": "2026-05-07T00:00:00Z",
                "completedAt": "2026-05-07T00:00:01Z",
                "stdout": "installed token=secret-value",
                "stderr": "",
                "truncated": False,
            }

    class RuntimeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *, json, headers):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            return RuntimeResponse()

    monkeypatch.setattr("app.services.marketplace_service.httpx.Client", RuntimeClient)

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert result.status == "success"
    assert result.error_code is None
    assert result.stdout == "installed token=[REDACTED]"
    assert captured["url"] == "http://workspace-runtime:3002/api/v1/internal/marketplace/install/execute"
    assert captured["headers"] == {"Authorization": "Bearer dev-internal-token"}
    payload = captured["payload"]
    assert payload["provider"] == "codex"
    assert payload["argv"][:4] == ["/home/developer/.npm-global/bin/codex", "plugin", "marketplace", "add"]
    assert payload["argv"][4] == "/marketplace-install/codex"
    assert payload["env"] == {"WORKSPACE_ID": "workspace-1"}
    activity = marketplace_service.list_activity("user-1")
    assert activity.items[0].action == "install"
    assert activity.items[0].status == "success"


def test_install_package_maps_runtime_timeout_result(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_marketplace_add=True),
        ),
    )

    class RuntimeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "timeout",
                "exitCode": None,
                "startedAt": "2026-05-07T00:00:00Z",
                "completedAt": "2026-05-07T00:02:00Z",
                "stdout": "partial",
                "stderr": "timed out",
                "truncated": True,
                "errorCode": "marketplace.install.timeout",
            }

    class RuntimeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *, json, headers):
            return RuntimeResponse()

    monkeypatch.setattr("app.services.marketplace_service.httpx.Client", RuntimeClient)

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert result.status == "timeout"
    assert result.error_code == "marketplace.install.timeout"
    assert result.stderr == "timed out"
    assert result.truncated is True


def test_install_package_treats_gemini_already_installed_as_success(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="gemini",
            package_id="workspace-tools",
            display_name="Workspace Tools",
            description="Gemini workspace tools",
        ),
    )
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/gemini",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_extension_install=True),
        ),
    )

    class RuntimeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "failed",
                "exitCode": 1,
                "stdout": "",
                "stderr": 'Extension "workspace-tools" is already installed. Please uninstall it first.\n',
                "truncated": False,
                "errorCode": "marketplace.install.command_failed",
            }

    class RuntimeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *, json, headers):
            return RuntimeResponse()

    monkeypatch.setattr("app.services.marketplace_service.httpx.Client", RuntimeClient)

    result = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="gemini",
            package_id="workspace-tools",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert result.status == "success"
    assert result.error_code is None
    assert "already installed" in result.stderr


def test_install_package_maps_adapter_command_build_failures(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    adapter = marketplace_service._get_adapter("codex")
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_marketplace_add=True),
        ),
    )
    monkeypatch.setattr(
        adapter,
        "build_install_command",
        lambda package_path, workspace_id, preflight: (_ for _ in ()).throw(
            NotImplementedError("marketplace.install.not_implemented")
        ),
    )

    missing_capability = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    monkeypatch.setattr(
        adapter,
        "build_install_command",
        lambda package_path, workspace_id, preflight: (_ for _ in ()).throw(OSError("missing cli")),
    )
    cli_unavailable = marketplace_service.install_package(
        "user-1",
        MarketplaceInstallRequest(
            provider="codex",
            package_id="figma-context",
            revision=created.revision,
            workspace_id="workspace-1",
        ),
    )

    assert missing_capability.status == "cliCapabilityMissing"
    assert missing_capability.error_code == "marketplace.install.cli_capability_missing"
    assert cli_unavailable.status == "cliUnavailable"
    assert cli_unavailable.error_code == "marketplace.install.cli_unavailable"


def test_install_package_rejects_shell_like_command_plan(marketplace_service, monkeypatch):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    adapter = marketplace_service._get_adapter("codex")
    monkeypatch.setattr(
        marketplace_service,
        "_resolve_install_runtime",
        lambda workspace_id: {
            "runtimeUrl": "http://workspace-runtime:3002",
            "errorCode": None,
        },
    )
    monkeypatch.setattr(
        marketplace_service,
        "_detect_cli_on_runtime",
        lambda provider, runtime_url: MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path="/home/developer/.npm-global/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_marketplace_add=True),
        ),
    )
    monkeypatch.setattr(
        adapter,
        "build_install_command",
        lambda package_path, workspace_id, preflight: MarketplaceInstallCommandPlan(
            provider="codex",
            argv=["codex", "plugin", "install", "figma-context", "&&", "echo", "unsafe"],
            cwd=str(package_path.parent),
            env={"WORKSPACE_ID": workspace_id},
        ),
    )

    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_service.install_package(
            "user-1",
            MarketplaceInstallRequest(
                provider="codex",
                package_id="figma-context",
                revision=created.revision,
                workspace_id="workspace-1",
            ),
        )

    assert exc_info.value.results[0]["code"] == "marketplace.install.command_plan_invalid"


def test_validate_install_command_plan_rejects_missing_cwd_and_invalid_env(marketplace_service):
    with pytest.raises(MarketplaceValidationError) as missing_cwd:
        marketplace_service._validate_install_command_plan(
            MarketplaceInstallCommandPlan(
                provider="codex",
                argv=["codex", "plugin", "install", "figma-context"],
                cwd="",
                env={"WORKSPACE_ID": "workspace-1"},
            ),
        )

    with pytest.raises(MarketplaceValidationError) as invalid_env:
        marketplace_service._validate_install_command_plan(
            MarketplaceInstallCommandPlan.model_construct(
                provider="codex",
                argv=["codex", "plugin", "install", "figma-context"],
                cwd="/tmp",
                env={"WORKSPACE_ID": 123},
            ),
        )

    assert missing_cwd.value.results[0]["code"] == "marketplace.install.command_plan_invalid"
    assert invalid_env.value.results[0]["code"] == "marketplace.install.command_plan_invalid"


def test_install_response_codes_have_localized_messages():
    translation_root = Path(__file__).parents[4] / "app" / "translations"
    required_keys = {
        "marketplace.install.success",
        "marketplace.install.validation_failed",
        "marketplace.install.command_failed",
        "marketplace.install.timeout",
        "marketplace.install.cli_unavailable",
        "marketplace.install.cli_version_unsupported",
        "marketplace.install.cli_capability_missing",
        "marketplace.install.runtime_unavailable",
        "marketplace.install.runtime_delegation_unavailable",
        "marketplace.install.runtime_invalid_cwd",
        "marketplace.install.workspace_not_found",
        "marketplace.install.workspace_not_running",
        "marketplace.install.runtime_url_missing",
        "marketplace.install.command_plan_invalid",
    }

    for locale in ["en", "zh-TW"]:
        messages = json.loads((translation_root / f"{locale}.json").read_text(encoding="utf-8"))
        missing = sorted(key for key in required_keys if not messages.get(key))
        assert missing == []


def test_import_as_new_requires_valid_new_package_id(marketplace_service):
    with pytest.raises(MarketplaceImportSourceError, match="marketplace.package.invalid_id"):
        marketplace_service._target_import_package_id(
            MarketplaceImportCandidate(
                id="codex:figma-context",
                provider="codex",
                package_id="figma-context",
                display_name="Figma Context",
                source_path="plugins/figma-context",
                duplicate=True,
                duplicate_action="import-as-new",
                new_package_id="../escape",
            ),
        )


def test_install_result_redacts_likely_secrets_before_returning_output(marketplace_service):
    request = MarketplaceInstallRequest(
        provider="codex",
        package_id="figma-context",
        revision="rev-1",
        workspace_id="workspace-1",
    )

    result = marketplace_service._install_result(
        request,
        "failed",
        "marketplace.install.command_failed",
        stdout="installed token=codex-secret Authorization: Bearer abc.def",
        stderr="password = super-secret api_key=abc123",
    )

    assert "codex-secret" not in result.stdout
    assert "abc.def" not in result.stdout
    assert "super-secret" not in result.stderr
    assert "abc123" not in result.stderr
    assert "token=[REDACTED]" in result.stdout
    assert "Bearer [REDACTED]" in result.stdout
    assert "password = [REDACTED]" in result.stderr
    assert "api_key=[REDACTED]" in result.stderr


def test_install_result_limits_output_by_utf8_bytes(marketplace_service):
    request = MarketplaceInstallRequest(
        provider="gemini",
        package_id="workspace-tools",
        revision="rev-1",
        workspace_id="workspace-1",
    )

    result = marketplace_service._install_result(
        request,
        "failed",
        "marketplace.install.command_failed",
        stdout="abcdef",
        stderr="錯誤錯誤",
        stdout_limit_bytes=4,
        stderr_limit_bytes=7,
    )

    assert result.stdout == "abcd"
    assert result.stderr == "錯誤"
    assert result.truncated is True


def test_sanitize_install_output_accepts_custom_redaction_patterns(marketplace_service):
    stdout, stderr, truncated = marketplace_service._sanitize_install_output(
        stdout="workspace=/private/tmp/source",
        stderr="ok",
        stdout_limit_bytes=100,
        stderr_limit_bytes=100,
        redact_patterns=[r"/private/tmp/[A-Za-z0-9_-]+"],
    )

    assert stdout == "workspace=[REDACTED]"
    assert stderr == "ok"
    assert truncated is False


def test_validate_import_source_allows_only_scoped_local_paths(marketplace_service):
    user_root = marketplace_service.get_registry_root("user-1").parent
    allowed_source = user_root / "import-sources" / "upstream"
    allowed_source.mkdir(parents=True)
    outside_source = marketplace_service.storage_root / "outside"
    outside_source.mkdir(parents=True)

    validated = marketplace_service.validate_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="codex",
            sourceKind="local",
            source=str(allowed_source),
        ),
    )

    assert validated["sourceKind"] == "local"
    assert validated["sourceRoot"] == allowed_source.resolve()
    with pytest.raises(MarketplaceImportSourceError) as exc_info:
        marketplace_service.validate_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="codex",
                sourceKind="local",
                source=str(outside_source),
            ),
        )
    assert exc_info.value.code == "marketplace.import.validation.local_path_not_allowed"


def test_validate_import_source_rejects_unsafe_git_inputs(marketplace_service):
    with pytest.raises(MarketplaceImportSourceError) as token_exc:
        marketplace_service.validate_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="codex",
                sourceKind="git",
                source="https://token@example.com/org/repo.git",
            ),
        )
    with pytest.raises(MarketplaceImportSourceError) as key_exc:
        marketplace_service.validate_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="codex",
                sourceKind="git",
                source="-----BEGIN OPENSSH PRIVATE KEY-----",
            ),
        )

    assert token_exc.value.code == "marketplace.import.validation.https_token_unsupported"
    assert key_exc.value.code == "marketplace.import.validation.raw_private_key_unsupported"


def test_validate_import_source_uses_registry_ssh_key_for_ssh_imports(marketplace_service):
    private_key_path = marketplace_service.get_registry_root("user-1") / ".marketplace" / "ssh" / "id_ed25519"
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_text("private", encoding="utf-8")
    marketplace_service.save_registry_ssh_key("user-1", {
        "publicKey": "ssh-ed25519 demo",
        "privateKeyPath": str(private_key_path),
        "fingerprint": "SHA256:demo",
    })

    validated = marketplace_service.validate_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="claude-code",
            sourceKind="git",
            source="git@github.com:org/repo.git",
        ),
    )

    assert validated["sourceKind"] == "git"
    assert validated["scheme"] == "ssh"
    assert validated["host"] == "github.com"
    assert validated["sshKeyPath"] == str(private_key_path)
    assert validated["workRoot"].is_dir()

    private_key_path.unlink()
    with pytest.raises(MarketplaceImportSourceError) as missing_key_exc:
        marketplace_service.validate_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="claude-code",
                sourceKind="git",
                source="git@github.com:org/repo.git",
            ),
        )

    assert missing_key_exc.value.code == "marketplace.import.validation.ssh_key_required"


def test_scan_import_source_clones_git_source_to_temporary_worktree_and_cleans_up(
    marketplace_service,
    monkeypatch,
):
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        Path(command[-1]).mkdir(parents=True)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    candidates = marketplace_service.scan_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="codex",
            sourceKind="git",
            source="https://example.com/org/repo.git",
        ),
    )
    work_root = marketplace_service.get_registry_root("user-1").parent / "import-worktrees"

    assert candidates == []
    assert commands[0][0] == [
        "git",
        "clone",
        "--depth",
        "1",
        "https://example.com/org/repo.git",
        commands[0][0][-1],
    ]
    assert commands[0][1]["capture_output"] is True
    assert commands[0][1]["timeout"] == 120
    assert work_root.is_dir()
    assert list(work_root.iterdir()) == []


def test_scan_import_source_returns_claude_external_candidates_from_allowed_local_source(marketplace_service):
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "claude-marketplace"
    manifest_path = source_root / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "review-assistant",
                "source": "./plugins/review-assistant",
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "review-assistant" / ".claude-plugin"
    package_path.mkdir(parents=True)
    (package_path / "plugin.json").write_text(
        json.dumps({"name": "review-assistant"}),
        encoding="utf-8",
    )

    candidates = marketplace_service.scan_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="claude-code",
            sourceKind="local",
            source=str(source_root),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].provider == "claude-code"
    assert candidates[0].package_id == "review-assistant"
    assert candidates[0].source_path == "plugins/review-assistant"
    assert candidates[0].duplicate is False
    assert candidates[0].validation_severity == "none"


def test_scan_import_source_returns_codex_external_candidates_from_allowed_local_source(marketplace_service):
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-marketplace"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "figma-context" / ".codex-plugin"
    package_path.mkdir(parents=True)
    (package_path / "plugin.json").write_text(
        json.dumps({
            "name": "figma-context",
            "version": "0.1.0",
            "description": "Figma context tools",
        }),
        encoding="utf-8",
    )

    candidates = marketplace_service.scan_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="codex",
            sourceKind="local",
            source=str(source_root),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].provider == "codex"
    assert candidates[0].package_id == "figma-context"
    assert candidates[0].source_path == "plugins/figma-context"
    assert candidates[0].duplicate is False
    assert candidates[0].validation_severity == "none"


def test_save_uploaded_import_source_extracts_zip_to_allowed_local_source(marketplace_service):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            ".agents/plugins/marketplace.json",
            json.dumps({
                "plugins": [{
                    "name": "uploaded-plugin",
                    "source": {"source": "local", "path": "./plugins/uploaded-plugin"},
                }],
            }),
        )
        archive.writestr(
            "plugins/uploaded-plugin/.codex-plugin/plugin.json",
            json.dumps({
                "name": "uploaded-plugin",
                "version": "0.1.0",
                "description": "Uploaded package",
            }),
        )

    upload = marketplace_service.save_uploaded_import_source(
        "user-1",
        "codex",
        "marketplace.zip",
        buffer.getvalue(),
    )

    assert upload.source.provider == "codex"
    assert upload.source.source_kind == "local"
    assert upload.file_name == "marketplace.zip"
    source_root = Path(upload.source.source)
    allowed_root = marketplace_service.get_registry_root("user-1").parent / "import-sources"
    source_root.relative_to(allowed_root)
    assert (source_root / "plugins" / "uploaded-plugin" / ".codex-plugin" / "plugin.json").exists()
    candidates = marketplace_service.scan_import_source("user-1", upload.source)
    assert [candidate.package_id for candidate in candidates] == ["uploaded-plugin"]


def test_scan_import_source_returns_gemini_external_candidates_from_allowed_local_source(marketplace_service):
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "gemini-marketplace"
    manifest_path = source_root / "extensions" / "workspace-tools" / "gemini-extension.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "name": "workspace-tools",
            "version": "0.1.0",
            "description": "Workspace package",
        }),
        encoding="utf-8",
    )

    candidates = marketplace_service.scan_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="gemini",
            sourceKind="local",
            source=str(source_root / "extensions"),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].provider == "gemini"
    assert candidates[0].package_id == "workspace-tools"
    assert candidates[0].source_path == "workspace-tools"
    assert candidates[0].duplicate is False
    assert candidates[0].validation_severity == "none"


def test_scan_import_source_marks_duplicate_candidates_skip_by_default(marketplace_service):
    marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Local package",
        ),
    )
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-duplicates"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "figma-context" / ".codex-plugin"
    package_path.mkdir(parents=True)
    (package_path / "plugin.json").write_text(
        json.dumps({
            "name": "figma-context",
            "version": "0.1.0",
            "description": "External package",
        }),
        encoding="utf-8",
    )

    candidates = marketplace_service.scan_import_source(
        "user-1",
        MarketplaceImportSource(
            provider="codex",
            sourceKind="local",
            source=str(source_root),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].duplicate is True
    assert candidates[0].duplicate_action == "skip"


def test_import_candidates_copies_codex_package_and_updates_manifest(marketplace_service):
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-copy"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
                "category": "design",
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "figma-context"
    (package_path / ".codex-plugin").mkdir(parents=True)
    (package_path / ".git" / "objects").mkdir(parents=True)
    (package_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (package_path / "README.md").write_text("# Imported\n", encoding="utf-8")
    (package_path / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({
            "name": "figma-context",
            "version": "0.1.0",
            "description": "External package",
        }),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(
        provider="codex",
        sourceKind="local",
        source=str(source_root),
    )
    candidates = marketplace_service.scan_import_source("user-1", source)

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )
    root = marketplace_service.get_registry_root("user-1")
    local_manifest = json.loads((root / "codex" / ".agents" / "plugins" / "marketplace.json").read_text())

    assert [item.package_id for item in result.imported] == ["figma-context"]
    assert result.imported[0].source_type == "imported"
    assert result.skipped == []
    assert result.failed == []
    assert (root / "codex" / "plugins" / "figma-context" / "README.md").read_text() == "# Imported\n"
    assert not (root / "codex" / "plugins" / "figma-context" / ".git").exists()
    assert local_manifest["plugins"][0]["name"] == "figma-context"
    assert local_manifest["plugins"][0]["source"] == {
        "source": "local",
        "path": "./plugins/figma-context",
    }
    assert local_manifest["plugins"][0]["category"] == "design"
    detail = marketplace_service.get_package_detail("user-1", "codex", "figma-context")
    assert detail.source_type == "imported"
    assert detail.manifest_metadata["sourceType"] == "imported"
    assert detail.manifest_metadata["importSource"] | {
        "importedAt": detail.manifest_metadata["importSource"]["importedAt"],
        "sourceIdentity": detail.manifest_metadata["importSource"]["sourceIdentity"],
    } == {
        "provider": "codex",
        "scanProvider": "codex",
        "sourceKind": "local",
        "source": str(source_root),
        "packageId": "figma-context",
        "targetPackageId": "figma-context",
        "sourcePath": "plugins/figma-context",
        "sourceMetadata": {},
        "importedAt": detail.manifest_metadata["importSource"]["importedAt"],
        "sourceIdentity": f"local:{source_root.resolve()}",
    }


def test_import_candidates_clones_nested_remote_claude_source(marketplace_service, monkeypatch):
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "claude-remote"
    manifest_path = source_root / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "remote-plugin",
                "source": {
                    "source": "git-subdir",
                    "url": "https://example.com/org/remote-plugin.git",
                    "path": "plugins/remote-plugin",
                    "ref": "main",
                    "sha": "abc123",
                },
                "category": "productivity",
            }],
        }),
        encoding="utf-8",
    )
    clone_calls = []

    def fake_clone_nested(url, checkout_root, *, ref=None, sha=None, ssh_key_path=None):
        clone_calls.append({
            "url": url,
            "ref": ref,
            "sha": sha,
            "sshKeyPath": ssh_key_path,
        })
        package_path = checkout_root / "plugins" / "remote-plugin"
        (package_path / ".claude-plugin").mkdir(parents=True)
        (package_path / "README.md").write_text("# Remote\n", encoding="utf-8")
        (package_path / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "remote-plugin"}),
            encoding="utf-8",
        )

    monkeypatch.setattr(marketplace_service, "_clone_nested_import_source", fake_clone_nested)
    source = MarketplaceImportSource(
        provider="claude-code",
        sourceKind="local",
        source=str(source_root),
    )
    candidates = marketplace_service.scan_import_source("user-1", source)

    assert candidates[0].source_path == "https://example.com/org/remote-plugin.git:plugins/remote-plugin"
    assert candidates[0].source_metadata == {
        "kind": "git",
        "sourceType": "git-subdir",
        "url": "https://example.com/org/remote-plugin.git",
        "path": "plugins/remote-plugin",
        "ref": "main",
        "sha": "abc123",
    }

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )
    root = marketplace_service.get_registry_root("user-1")
    local_manifest = json.loads((root / "claude-code" / ".claude-plugin" / "marketplace.json").read_text())
    detail = marketplace_service.get_package_detail("user-1", "claude-code", "remote-plugin")

    assert [item.package_id for item in result.imported] == ["remote-plugin"]
    assert result.failed == []
    assert clone_calls == [{
        "url": "https://example.com/org/remote-plugin.git",
        "ref": "main",
        "sha": "abc123",
        "sshKeyPath": None,
    }]
    assert (root / "claude-code" / "plugins" / "remote-plugin" / "README.md").read_text() == "# Remote\n"
    assert local_manifest["plugins"][0]["name"] == "remote-plugin"
    assert local_manifest["plugins"][0]["source"] == "./plugins/remote-plugin"
    assert local_manifest["plugins"][0]["category"] == "productivity"
    assert detail.manifest_metadata["importSource"]["sourceMetadata"] == candidates[0].source_metadata


def test_import_candidates_skips_duplicate_by_default(marketplace_service):
    marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Local package",
        ),
    )
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-skip"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "figma-context" / ".codex-plugin"
    package_path.mkdir(parents=True)
    (package_path / "plugin.json").write_text(
        json.dumps({
            "name": "figma-context",
            "version": "0.2.0",
            "description": "External package",
        }),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidates = marketplace_service.scan_import_source("user-1", source)

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )

    assert result.imported == []
    assert len(result.skipped) == 1
    assert result.skipped[0].duplicate is True
    assert result.failed == []


def test_import_candidates_reports_overwrite_revision_conflict(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Local package",
        ),
    )
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-overwrite"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "figma-context" / ".codex-plugin"
    package_path.mkdir(parents=True)
    (package_path / "plugin.json").write_text(
        json.dumps({
            "name": "figma-context",
            "version": "0.2.0",
            "description": "External package",
        }),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidate = marketplace_service.scan_import_source("user-1", source)[0].model_copy(update={
        "duplicate_action": "overwrite",
        "local_revision": "stale",
    })

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=[candidate]),
    )

    assert result.imported == []
    assert result.failed[0].error_code == "marketplace.package.revision_conflict"
    assert marketplace_service.get_package_detail("user-1", "codex", "figma-context").revision == created.revision


def test_import_candidates_imports_duplicate_as_new_id(marketplace_service):
    marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Local package",
        ),
    )
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-new-id"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
                "description": "External package",
            }],
        }),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "figma-context" / ".codex-plugin"
    package_path.mkdir(parents=True)
    (package_path / "plugin.json").write_text(
        json.dumps({
            "name": "figma-context",
            "version": "0.2.0",
            "description": "External package",
        }),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidate = marketplace_service.scan_import_source("user-1", source)[0].model_copy(update={
        "duplicate_action": "import-as-new",
        "new_package_id": "figma-context-copy",
    })

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=[candidate]),
    )
    root = marketplace_service.get_registry_root("user-1")
    imported_manifest = json.loads(
        (root / "codex" / "plugins" / "figma-context-copy" / ".codex-plugin" / "plugin.json").read_text(),
    )

    assert [item.package_id for item in result.imported] == ["figma-context-copy"]
    assert imported_manifest["name"] == "figma-context-copy"
    assert imported_manifest["sourceType"] == "imported"
    assert imported_manifest["importSource"]["packageId"] == "figma-context"
    assert imported_manifest["importSource"]["targetPackageId"] == "figma-context-copy"


def test_import_candidates_synthesizes_manifest_when_listing_only(marketplace_service):
    """Anthropic's official Claude Code marketplace ships listings without
    per-package plugin.json (e.g. csharp-lsp). The import flow must seed a
    self-contained plugin.json from the marketplace listing entry."""
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "claude-listing-only"
    manifest_path = source_root / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [{
                "name": "csharp-lsp",
                "source": "./plugins/csharp-lsp",
                "description": "C# language server for code intelligence",
                "version": "1.0.0",
                "category": "development",
                "author": {"name": "Anthropic", "email": "support@anthropic.com"},
                "lspServers": {"csharp-ls": {"command": "csharp-ls"}},
            }],
        }),
        encoding="utf-8",
    )
    (source_root / "plugins" / "csharp-lsp").mkdir(parents=True)
    (source_root / "plugins" / "csharp-lsp" / "README.md").write_text("# csharp-lsp", encoding="utf-8")
    (source_root / "plugins" / "csharp-lsp" / "LICENSE").write_text("MIT", encoding="utf-8")

    source = MarketplaceImportSource(provider="claude-code", sourceKind="local", source=str(source_root))
    candidates = marketplace_service.scan_import_source("user-1", source)

    assert len(candidates) == 1
    assert candidates[0].validation_severity == "none"

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )

    assert result.failed == []
    assert [item.package_id for item in result.imported] == ["csharp-lsp"]

    registry_root = marketplace_service.get_registry_root("user-1")
    seeded_manifest = json.loads(
        (registry_root / "claude-code" / "plugins" / "csharp-lsp" / ".claude-plugin" / "plugin.json").read_text()
    )
    assert seeded_manifest["name"] == "csharp-lsp"
    assert seeded_manifest["description"] == "C# language server for code intelligence"
    assert seeded_manifest["version"] == "1.0.0"
    assert seeded_manifest["category"] == "development"
    assert seeded_manifest["lspServers"] == {"csharp-ls": {"command": "csharp-ls"}}
    assert seeded_manifest["sourceType"] == "imported"


def test_import_candidates_rolls_back_failed_candidate_after_success(marketplace_service):
    user_root = marketplace_service.get_registry_root("user-1").parent
    source_root = user_root / "import-sources" / "codex-partial"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({
            "plugins": [
                {"name": "first-plugin", "source": {"source": "local", "path": "./plugins/first-plugin"}},
                {"name": "broken-plugin", "source": {"source": "local", "path": "./plugins/broken-plugin"}},
            ],
        }),
        encoding="utf-8",
    )
    first_path = source_root / "plugins" / "first-plugin" / ".codex-plugin"
    first_path.mkdir(parents=True)
    (first_path / "plugin.json").write_text(
        json.dumps({"name": "first-plugin", "version": "0.1.0", "description": "First"}),
        encoding="utf-8",
    )
    broken_path = source_root / "plugins" / "broken-plugin"
    broken_path.mkdir(parents=True)
    (broken_path / ".codex-plugin").mkdir()
    (broken_path / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "broken-plugin", "version": "0.1.0", "description": "Broken"}),
        encoding="utf-8",
    )
    (broken_path / "escape").symlink_to(source_root)
    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidates = marketplace_service.scan_import_source("user-1", source)

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )
    root = marketplace_service.get_registry_root("user-1")
    local_manifest = json.loads((root / "codex" / ".agents" / "plugins" / "marketplace.json").read_text())

    assert [item.package_id for item in result.imported] == ["first-plugin"]
    assert result.failed[0].package_id == "broken-plugin"
    assert result.failed[0].error_code == "marketplace.package.symlink_rejected"
    assert (root / "codex" / "plugins" / "first-plugin").is_dir()
    assert not (root / "codex" / "plugins" / "broken-plugin").exists()
    assert [entry["name"] for entry in local_manifest["plugins"]] == ["first-plugin"]


def test_scan_import_source_reports_clone_failure_and_cleans_up(marketplace_service, monkeypatch):
    checkout_paths = []

    def fake_run(command, **kwargs):
        checkout = Path(command[-1])
        checkout.mkdir(parents=True)
        checkout_paths.append(checkout)
        return SimpleNamespace(returncode=128)

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    with pytest.raises(MarketplaceImportSourceError) as exc_info:
        marketplace_service.scan_import_source(
            "user-1",
            MarketplaceImportSource(
                provider="codex",
                sourceKind="git",
                source="https://example.com/org/repo.git",
            ),
        )
    work_root = marketplace_service.get_registry_root("user-1").parent / "import-worktrees"

    assert exc_info.value.code == "marketplace.import.validation.clone_failed"
    assert checkout_paths
    assert not checkout_paths[0].exists()
    assert list(work_root.iterdir()) == []


def test_clone_import_source_trims_repository_url(marketplace_service, monkeypatch, tmp_path):
    captured_command = []

    def fake_run(command, **kwargs):
        captured_command.extend(command)
        Path(command[-1]).mkdir(parents=True)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    marketplace_service._clone_import_source(
        MarketplaceImportSource(
            provider="claude-code",
            sourceKind="git",
            source=" https://github.com/obra/superpowers \n",
        ),
        tmp_path / "checkout",
    )

    assert captured_command[-2] == "https://github.com/obra/superpowers"


def test_git_source_identity_normalizes_url_variants(marketplace_service):
    assert marketplace_service._normalize_git_source_identity("https://github.com/obra/superpowers") == (
        "github.com/obra/superpowers"
    )
    assert marketplace_service._normalize_git_source_identity("https://github.com/obra/superpowers.git") == (
        "github.com/obra/superpowers"
    )
    assert marketplace_service._normalize_git_source_identity("git@github.com:obra/superpowers.git") == (
        "github.com/obra/superpowers"
    )


def test_import_allows_internal_symlink_by_copying_target_file(marketplace_service, tmp_path):
    source_root = marketplace_service.get_registry_root("user-1").parent / "import-sources" / "source"
    plugin_root = source_root / "plugins" / "linked-plugin"
    manifest_root = source_root / ".agents" / "plugins"
    manifest_root.mkdir(parents=True)
    plugin_root.mkdir(parents=True)
    (manifest_root / "marketplace.json").write_text(
        json.dumps({
            "plugins": [{
                "name": "linked-plugin",
                "source": {"source": "local", "path": "./plugins/linked-plugin"},
            }],
        }),
        encoding="utf-8",
    )
    (plugin_root / ".codex-plugin").mkdir()
    (plugin_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "linked-plugin", "version": "0.1.0", "description": "Linked"}),
        encoding="utf-8",
    )
    (plugin_root / "TARGET.md").write_text("linked content", encoding="utf-8")
    (plugin_root / "AGENTS.md").symlink_to("TARGET.md")

    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidates = marketplace_service.scan_import_source("user-1", source)
    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )
    imported_root = marketplace_service.resolve_package_path("user-1", "codex", "linked-plugin")

    assert [item.package_id for item in result.imported] == ["linked-plugin"]
    assert result.failed == []
    assert (imported_root / "AGENTS.md").read_text(encoding="utf-8") == "linked content"
    assert not (imported_root / "AGENTS.md").is_symlink()


def test_import_all_provider_source_tracks_family_variants(marketplace_service):
    source_root = marketplace_service.get_registry_root("user-1").parent / "import-sources" / "multi-provider"
    claude_marketplace = source_root / ".claude-plugin" / "marketplace.json"
    codex_marketplace = source_root / ".agents" / "plugins" / "marketplace.json"
    claude_marketplace.parent.mkdir(parents=True)
    codex_marketplace.parent.mkdir(parents=True)
    claude_marketplace.write_text(
        json.dumps({
            "plugins": [{
                "name": "superpowers",
                "source": "./",
                "description": "Core skills library",
                "version": "1.0.0",
            }],
        }),
        encoding="utf-8",
    )
    codex_marketplace.write_text(
        json.dumps({
            "plugins": [{
                "name": "superpowers",
                "source": {"source": "local", "path": "./"},
                "description": "Core skills library",
                "version": "1.0.0",
            }],
        }),
        encoding="utf-8",
    )
    (source_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "superpowers", "description": "Core skills library", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (source_root / ".codex-plugin").mkdir()
    (source_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "superpowers", "description": "Core skills library", "version": "1.0.0"}),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(provider="all", sourceKind="local", source=str(source_root))

    candidates = marketplace_service.scan_import_source("user-1", source)
    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )
    listed = marketplace_service.list_packages("user-1")
    detail = marketplace_service.get_package_detail("user-1", "codex", "superpowers")

    assert [(candidate.provider, candidate.package_id) for candidate in candidates] == [
        ("claude-code", "superpowers"),
        ("codex", "superpowers"),
    ]
    assert {candidate.variant_status for candidate in candidates} == {"new-family"}
    assert {candidate.family_id for candidate in candidates} == {f"local:{source_root.resolve()}"}
    assert all(len(candidate.variants) == 2 for candidate in candidates)
    assert [(item.provider, item.package_id) for item in result.imported] == [
        ("claude-code", "superpowers"),
        ("codex", "superpowers"),
    ]
    assert all(len(item.variants) == 2 for item in result.imported)
    assert {item.family_id for item in listed.items} == {f"local:{source_root.resolve()}"}
    assert all(len(item.variants) == 2 for item in listed.items)
    assert detail is not None
    assert len(detail.variants) == 2


def test_import_marks_missing_provider_as_additive_variant(marketplace_service):
    source_root = marketplace_service.get_registry_root("user-1").parent / "import-sources" / "add-variant"
    (source_root / ".claude-plugin").mkdir(parents=True)
    (source_root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "superpowers", "source": "./"}]}),
        encoding="utf-8",
    )
    (source_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "superpowers", "description": "Core skills library"}),
        encoding="utf-8",
    )
    (source_root / ".agents" / "plugins").mkdir(parents=True)
    (source_root / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "superpowers", "source": {"source": "local", "path": "./"}}]}),
        encoding="utf-8",
    )
    (source_root / ".codex-plugin").mkdir()
    (source_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "superpowers", "version": "1.0.0", "description": "Core skills library"}),
        encoding="utf-8",
    )

    claude_source = MarketplaceImportSource(provider="claude-code", sourceKind="local", source=str(source_root))
    claude_candidate = marketplace_service.scan_import_source("user-1", claude_source)[0]
    marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=claude_source, candidates=[claude_candidate]),
    )

    codex_source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    codex_candidate = marketplace_service.scan_import_source("user-1", codex_source)[0]

    assert codex_candidate.duplicate is False
    assert codex_candidate.variant_status == "add-variant"
    assert codex_candidate.family_id == f"local:{source_root.resolve()}"


def test_import_marks_existing_provider_as_duplicate_variant(marketplace_service):
    source_root = marketplace_service.get_registry_root("user-1").parent / "import-sources" / "duplicate-variant"
    (source_root / ".codex-plugin").mkdir(parents=True)
    (source_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "superpowers", "version": "1.0.0", "description": "Core skills library"}),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidate = marketplace_service.scan_import_source("user-1", source)[0]
    marketplace_service.import_candidates("user-1", MarketplaceImportRequest(source=source, candidates=[candidate]))

    rescanned = marketplace_service.scan_import_source("user-1", source)[0]

    assert rescanned.duplicate is True
    assert rescanned.variant_status == "duplicate-variant"
    assert rescanned.local_revision


def test_import_rolls_back_package_listing_and_family_metadata_failure(marketplace_service, monkeypatch):
    source_root = marketplace_service.get_registry_root("user-1").parent / "import-sources" / "rollback-family"
    (source_root / ".codex-plugin").mkdir(parents=True)
    (source_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "rollback-plugin", "version": "1.0.0", "description": "Rollback test"}),
        encoding="utf-8",
    )
    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidate = marketplace_service.scan_import_source("user-1", source)[0]

    def fail_family_write(*_args, **_kwargs):
        raise OSError("family metadata write failed")

    monkeypatch.setattr(marketplace_service, "_write_package_families", fail_family_write)

    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=[candidate]),
    )
    package_path = marketplace_service.resolve_package_path("user-1", "codex", "rollback-plugin")
    listed = marketplace_service.list_packages("user-1")

    assert result.imported == []
    assert [(item.package_id, item.error_code) for item in result.failed] == [
        ("rollback-plugin", "marketplace.import.validation.copy_failed"),
    ]
    assert not package_path.exists()
    assert listed.items == []
    assert marketplace_service._read_package_families(marketplace_service.get_registry_root("user-1")).families == []


def test_import_codex_root_plugin_without_marketplace_manifest_appears_in_list(marketplace_service):
    source_root = marketplace_service.get_registry_root("user-1").parent / "import-sources" / "codex-root"
    (source_root / ".codex-plugin").mkdir(parents=True)
    (source_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({
            "name": "superpowers",
            "version": "1.0.0",
            "description": "Core skills library",
        }),
        encoding="utf-8",
    )

    source = MarketplaceImportSource(provider="codex", sourceKind="local", source=str(source_root))
    candidates = marketplace_service.scan_import_source("user-1", source)
    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=source, candidates=candidates),
    )
    listed = marketplace_service.list_packages("user-1", provider="codex")

    assert [candidate.package_id for candidate in candidates] == ["superpowers"]
    assert [item.package_id for item in result.imported] == ["superpowers"]
    assert [item.package_id for item in listed.items] == ["superpowers"]


def test_export_package_returns_provider_native_zip_and_rejects_symlink(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="gemini",
            package_id="workspace-tools",
            display_name="Workspace Tools",
            description="Workspace package",
        ),
    )
    archive = marketplace_service.export_package("user-1", created.provider, created.package_id, created.revision)

    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        assert "gemini-extension.json" in zip_file.namelist()
        assert "GEMINI.md" in zip_file.namelist()

    package_root = marketplace_service.resolve_package_path("user-1", "gemini", "workspace-tools")
    (package_root / "unsafe-link").symlink_to(package_root / "GEMINI.md")
    unsafe_detail = marketplace_service.get_package_detail("user-1", "gemini", "workspace-tools")
    with pytest.raises(Exception, match="marketplace.package.symlink_rejected"):
        marketplace_service.export_package("user-1", "gemini", "workspace-tools", unsafe_detail.revision)


def test_export_package_requires_current_revision(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )

    with pytest.raises(MarketplaceConflictError, match="marketplace.package.revision_conflict"):
        marketplace_service.export_package("user-1", "codex", created.package_id, "stale")


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
        (
            "gemini",
            "workspace-tools",
            {
                "gemini-extension.json",
                "GEMINI.md",
            },
        ),
    ],
)
def test_export_package_archives_scan_and_import_round_trip(
    marketplace_service,
    provider,
    package_id,
    expected_entries,
):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider=provider,
            package_id=package_id,
            display_name="Exported Package",
            description="Exported package",
        ),
    )
    archive_bytes = marketplace_service.export_package("user-1", provider, package_id, created.revision)

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
    assert expected_entries.issubset(names)

    marketplace_service.delete_package(
        "user-1",
        MarketplacePackageDeleteRequest(
            provider=provider,
            package_id=package_id,
            revision=created.revision,
        ),
    )
    upload = marketplace_service.save_uploaded_import_source(
        "user-1",
        provider,
        f"{provider}-{package_id}.zip",
        archive_bytes,
    )
    candidates = marketplace_service.scan_import_source("user-1", upload.source)
    result = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=upload.source, candidates=candidates),
    )

    assert [candidate.package_id for candidate in candidates] == [package_id]
    assert [item.package_id for item in result.imported] == [package_id]
    assert result.failed == []
    assert marketplace_service.get_package_detail("user-1", provider, package_id) is not None


def test_exported_archive_duplicate_actions_use_import_flow(marketplace_service):
    created = marketplace_service.create_package(
        "user-1",
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma MCP package",
        ),
    )
    archive_bytes = marketplace_service.export_package("user-1", "codex", "figma-context", created.revision)
    upload = marketplace_service.save_uploaded_import_source(
        "user-1",
        "codex",
        "codex-figma-context.zip",
        archive_bytes,
    )

    skipped_candidate = marketplace_service.scan_import_source("user-1", upload.source)[0]
    skipped = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=upload.source, candidates=[skipped_candidate]),
    )
    assert skipped.imported == []
    assert [candidate.package_id for candidate in skipped.skipped] == ["figma-context"]

    overwrite_candidate = marketplace_service.scan_import_source("user-1", upload.source)[0].model_copy(update={
        "duplicate_action": "overwrite",
    })
    overwritten = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=upload.source, candidates=[overwrite_candidate]),
    )
    assert [item.package_id for item in overwritten.imported] == ["figma-context"]

    copy_candidate = marketplace_service.scan_import_source("user-1", upload.source)[0].model_copy(update={
        "duplicate_action": "import-as-new",
        "new_package_id": "figma-context-copy",
    })
    copied = marketplace_service.import_candidates(
        "user-1",
        MarketplaceImportRequest(source=upload.source, candidates=[copy_candidate]),
    )

    assert [item.package_id for item in copied.imported] == ["figma-context-copy"]
    assert marketplace_service.get_package_detail("user-1", "codex", "figma-context-copy") is not None
