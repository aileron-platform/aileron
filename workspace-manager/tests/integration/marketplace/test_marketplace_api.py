"""Marketplace API tests."""

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import models as db_models


def _marketplace_registry_root() -> Path:
    return Path(os.environ["MARKETPLACE_STORAGE_PATH"]) / "registry"


def test_marketplace_registry_init_and_settings_save(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    response = client.post("/api/v1/marketplace/registry/init")

    assert response.status_code == 201
    body = response.json()
    root = Path(body["rootPath"])
    assert body["claudeManifestPath"] == "claude-code/.claude-plugin/marketplace.json"
    assert body["codexManifestPath"] == "codex/.agents/plugins/marketplace.json"
    assert body["geminiRootPath"] == "gemini"
    assert root.is_relative_to(Path(os.environ["MARKETPLACE_STORAGE_PATH"]))

    payload = {
        "name": "Team Marketplace",
        "owner": {
            "name": "Team Maintainer",
            "email": "team@example.local",
        },
        "description": "Team package registry",
    }
    save_response = client.put("/api/v1/marketplace/settings", json=payload)

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["settings"]["displayName"] == "Team Marketplace"
    assert saved["settings"]["maintainerName"] == "Team Maintainer"
    assert saved["settings"]["maintainerEmail"] == "team@example.local"
    assert saved["settings"]["description"] == "Team package registry"
    assert saved["claudeWritten"] is True
    assert saved["codexWritten"] is True

    claude = json.loads((root / "claude-code" / ".claude-plugin" / "marketplace.json").read_text())
    codex = json.loads((root / "codex" / ".agents" / "plugins" / "marketplace.json").read_text())
    assert claude["owner"] == {"name": "Team Maintainer", "email": "team@example.local"}
    assert claude["plugins"] == []
    assert codex["name"] == "Team-Marketplace"
    assert "owner" not in codex
    assert codex["plugins"] == []


def test_marketplace_package_list_and_detail_scan_registry(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/init")
    root = Path(init_response.json()["rootPath"])
    manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plugins"] = [{
        "name": "figma-context",
        "source": {"source": "local", "path": "./plugins/figma-context"},
        "category": "design",
        "tags": ["mcp"],
    }]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    package_root = root / "codex" / "plugins" / "figma-context"
    (package_root / ".codex-plugin").mkdir(parents=True)
    (package_root / "skills" / "review").mkdir(parents=True)
    (package_root / "skills" / "review" / "SKILL.md").write_text("# Review\n", encoding="utf-8")
    (package_root / "README.md").write_text("# Figma Context\n", encoding="utf-8")
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "figma-context", "version": "0.2.0", "description": "Figma MCP package"}),
        encoding="utf-8",
    )

    list_response = client.get("/api/v1/marketplace/packages?provider=codex&features=skills")

    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["items"][0]["packageId"] == "figma-context"
    assert listed["items"][0]["validationSeverity"] == "none"

    detail_response = client.get("/api/v1/marketplace/packages/codex/figma-context")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["manifestMetadata"]["version"] == "0.2.0"
    assert detail["readmeMarkdown"] == "# Figma Context\n"
    assert detail["featureContent"]["skills"][0]["path"] == "skills/review/SKILL.md"
    assert [item["path"] for item in detail["packageFiles"]] == [
        ".codex-plugin/plugin.json",
        "README.md",
        "skills/review/SKILL.md",
    ]


def test_marketplace_package_refresh_endpoint_returns_registry_fingerprint(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/init")
    root = Path(init_response.json()["rootPath"])
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

    refresh_response = client.post("/api/v1/marketplace/packages/refresh")

    assert refresh_response.status_code == 200
    body = refresh_response.json()
    assert body["total"] == 1
    assert body["registryFingerprint"]


def test_marketplace_registry_git_lifecycle_endpoints(test_app, tmp_path):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    remote_path = tmp_path / "registry.git"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True, capture_output=True, text=True)

    status_response = client.get("/api/v1/marketplace/registry/repository")
    init_response = client.post(
        "/api/v1/marketplace/registry/git/init",
        json={"remoteUrl": str(remote_path)},
    )
    remote_response = client.put(
        "/api/v1/marketplace/registry/remote",
        json={"remoteUrl": str(remote_path)},
    )
    assert status_response.status_code == 200
    assert status_response.json()["isGitRepo"] is False
    assert init_response.status_code == 200
    assert init_response.json()["success"] is True
    assert init_response.json()["repository"]["isGitRepo"] is True
    assert init_response.json()["repository"]["remoteUrl"] == str(remote_path)
    assert remote_response.status_code == 200
    assert remote_response.json()["messageKey"] == "marketplace.git.remote_update_success"


def test_marketplace_registry_status_endpoint_returns_provider_prefixed_changes(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/git/init")
    assert init_response.status_code == 200
    root = _marketplace_registry_root()
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Initial registry"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({"name": "Changed Registry", "description": "Changed", "plugins": []}),
        encoding="utf-8",
    )
    readme_path = root / "claude-code" / "plugins" / "review-assistant" / "README.md"
    readme_path.parent.mkdir(parents=True)
    readme_path.write_text("# Review\n", encoding="utf-8")
    gemini_path = root / "gemini" / "extensions" / "workspace-tools" / "gemini-extension.json"
    gemini_path.parent.mkdir(parents=True)
    gemini_path.write_text(json.dumps({"name": "workspace-tools"}), encoding="utf-8")
    subprocess.run(
        ["git", "add", "gemini/extensions/workspace-tools/gemini-extension.json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    response = client.get("/api/v1/marketplace/registry/status")

    assert response.status_code == 200
    body = response.json()
    assert body["isGitRepo"] is True
    assert body["branch"]
    assert body["staged"] == [{
        "path": "gemini/extensions/workspace-tools/gemini-extension.json",
        "status": "A",
        "type": "added",
        "oldPath": None,
    }]
    assert body["unstaged"][0]["path"] == "codex/.agents/plugins/marketplace.json"
    assert body["untracked"][0]["path"] == "claude-code/plugins/review-assistant/README.md"


def test_marketplace_registry_diff_endpoints_return_selected_file_patches(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/git/init")
    assert init_response.status_code == 200
    root = _marketplace_registry_root()
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Initial registry"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({"name": "Changed Registry", "description": "Changed", "plugins": []}, indent=2),
        encoding="utf-8",
    )

    worktree_response = client.get(
        "/api/v1/marketplace/registry/diff",
        params={"path": "codex/.agents/plugins/marketplace.json"},
    )
    subprocess.run(
        ["git", "add", "codex/.agents/plugins/marketplace.json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    index_response = client.get(
        "/api/v1/marketplace/registry/diff",
        params={"path": "codex/.agents/plugins/marketplace.json", "head": "INDEX"},
    )
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.local", "commit", "-m", "Update codex registry"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit_id = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commit_response = client.get(
        f"/api/v1/marketplace/registry/commits/{commit_id}/diff",
        params={"path": "codex/.agents/plugins/marketplace.json"},
    )
    commit_files_response = client.get(f"/api/v1/marketplace/registry/commits/{commit_id}/files")
    escape_response = client.get("/api/v1/marketplace/registry/diff", params={"path": "../outside.json"})

    assert worktree_response.status_code == 200
    assert worktree_response.json()["head"] == "WORKTREE"
    assert "+  \"name\": \"Changed Registry\"" in worktree_response.json()["patch"]
    assert index_response.status_code == 200
    assert index_response.json()["head"] == "INDEX"
    assert "+  \"name\": \"Changed Registry\"" in index_response.json()["patch"]
    assert commit_response.status_code == 200
    assert commit_response.json()["commitId"] == commit_id
    assert "+  \"name\": \"Changed Registry\"" in commit_response.json()["patch"]
    assert commit_files_response.status_code == 200
    assert commit_files_response.json()["files"][0]["path"] == "codex/.agents/plugins/marketplace.json"
    assert escape_response.status_code == 400


def test_marketplace_registry_stage_unstage_commit_and_history_endpoints(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/git/init")
    assert init_response.status_code == 200
    root = _marketplace_registry_root()
    empty_response = client.post("/api/v1/marketplace/registry/commit", json={"message": "Nothing"})
    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({"name": "Changed Registry", "description": "Changed", "plugins": []}, indent=2),
        encoding="utf-8",
    )

    stage_response = client.post(
        "/api/v1/marketplace/registry/stage",
        json={"paths": ["codex/.agents/plugins/marketplace.json"]},
    )
    unstage_response = client.post(
        "/api/v1/marketplace/registry/unstage",
        json={"paths": ["codex/.agents/plugins/marketplace.json"]},
    )
    commit_response = client.post(
        "/api/v1/marketplace/registry/commit",
        json={
            "message": "Update codex registry",
            "paths": ["codex/.agents/plugins/marketplace.json"],
        },
    )
    history_response = client.get("/api/v1/marketplace/registry/commits", params={"pageSize": 10})

    assert empty_response.status_code == 200
    assert empty_response.json()["success"] is False
    assert empty_response.json()["errorCode"] == "marketplace.git.no_changes_to_commit"
    assert stage_response.status_code == 200
    assert stage_response.json()["staged"][0]["path"] == "codex/.agents/plugins/marketplace.json"
    assert unstage_response.status_code == 200
    assert unstage_response.json()["stagedCount"] == 0
    assert "codex/.agents/plugins/marketplace.json" in [
        item["path"] for item in unstage_response.json()["untracked"]
    ]
    assert commit_response.status_code == 200
    assert commit_response.json()["success"] is True
    assert commit_response.json()["commit"]["message"] == "Update codex registry"
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
    assert history_response.json()["items"][0]["id"] == commit_response.json()["commit"]["id"]


def test_marketplace_registry_remote_sync_endpoints(test_app, tmp_path):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    remote = tmp_path / "registry.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    init_response = client.post("/api/v1/marketplace/registry/git/init", json={"remoteUrl": str(remote)})
    assert init_response.status_code == 200
    root = _marketplace_registry_root()
    codex_manifest = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps({"name": "Changed Registry", "description": "Changed", "plugins": []}, indent=2),
        encoding="utf-8",
    )
    commit_response = client.post(
        "/api/v1/marketplace/registry/commit",
        json={
            "message": "Initial registry",
            "paths": ["codex/.agents/plugins/marketplace.json"],
        },
    )
    push_response = client.post("/api/v1/marketplace/registry/push")
    peer = tmp_path / "peer"
    subprocess.run(["git", "clone", str(remote), str(peer)], check=True, capture_output=True, text=True)
    (peer / "REMOTE.md").write_text("# Remote\n", encoding="utf-8")
    subprocess.run(["git", "add", "REMOTE.md"], cwd=peer, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Peer", "-c", "user.email=peer@example.local", "commit", "-m", "Remote update"],
        cwd=peer,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "push", "origin", "HEAD"], cwd=peer, check=True, capture_output=True, text=True)

    fetch_response = client.post("/api/v1/marketplace/registry/fetch")
    pull_response = client.post("/api/v1/marketplace/registry/pull")

    assert commit_response.status_code == 200
    assert commit_response.json()["success"] is True
    assert push_response.status_code == 200
    assert push_response.json()["messageKey"] == "marketplace.git.push_success"
    assert fetch_response.status_code == 200
    assert fetch_response.json()["messageKey"] == "marketplace.git.fetch_success"
    assert pull_response.status_code == 200
    assert pull_response.json()["messageKey"] == "marketplace.git.pull_success"
    assert (root / "REMOTE.md").read_text(encoding="utf-8") == "# Remote\n"


def test_marketplace_registry_ssh_key_endpoints_return_public_metadata_only(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    missing_response = client.get("/api/v1/marketplace/registry/ssh-key")
    generate_response = client.post("/api/v1/marketplace/registry/ssh-key")
    loaded_response = client.get("/api/v1/marketplace/registry/ssh-key")

    assert missing_response.status_code == 200
    assert missing_response.json()["exists"] is False
    assert generate_response.status_code == 200
    generated = generate_response.json()
    assert generated["exists"] is True
    assert generated["algorithm"] == "ed25519"
    assert generated["publicKey"].startswith("ssh-ed25519 ")
    assert generated["fingerprint"].startswith("SHA256:")
    assert "privateKey" not in generated
    assert loaded_response.status_code == 200
    assert loaded_response.json() == generated


def test_marketplace_registry_unsupported_git_operations_return_localized_codes(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    endpoints = {
        "/api/v1/marketplace/registry/branches": "marketplace.git.branch_create_unsupported",
        "/api/v1/marketplace/registry/checkout": "marketplace.git.branch_switch_unsupported",
        "/api/v1/marketplace/registry/merge": "marketplace.git.merge_unsupported",
        "/api/v1/marketplace/registry/rebase": "marketplace.git.rebase_unsupported",
        "/api/v1/marketplace/registry/cherry-pick": "marketplace.git.cherry_pick_unsupported",
        "/api/v1/marketplace/registry/stash": "marketplace.git.stash_unsupported",
        "/api/v1/marketplace/registry/conflicts/resolve": "marketplace.git.conflict_resolution_unsupported",
    }

    responses = {path: client.post(path) for path in endpoints}

    for path, response in responses.items():
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == endpoints[path]
        assert response.json()["detail"]["message"]


def test_marketplace_package_list_endpoint_applies_filters_and_pagination(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/init")
    root = Path(init_response.json()["rootPath"])
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

    paged_response = client.get("/api/v1/marketplace/packages", params={"pageSize": 1})
    provider_response = client.get("/api/v1/marketplace/packages", params={"provider": "codex"})
    category_response = client.get("/api/v1/marketplace/packages", params={"category": "quality"})
    feature_response = client.get("/api/v1/marketplace/packages", params={"features": "commands"})
    query_response = client.get("/api/v1/marketplace/packages", params={"q": "review"})

    assert paged_response.status_code == 200
    paged = paged_response.json()
    assert paged["total"] == 2
    assert paged["pageSize"] == 1
    assert paged["totalPages"] == 2
    assert paged["categories"] == ["design", "quality"]
    assert paged["sourceTypes"] == ["created"]
    assert paged["validationSeverities"] == ["none"]
    assert [item["packageId"] for item in provider_response.json()["items"]] == ["figma-context"]
    assert [item["packageId"] for item in category_response.json()["items"]] == ["review-assistant"]
    assert [item["packageId"] for item in feature_response.json()["items"]] == ["figma-context"]
    assert [item["packageId"] for item in query_response.json()["items"]] == ["review-assistant"]


def test_marketplace_package_create_save_delete_and_export(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Figma Context",
        "description": "Figma MCP package",
    })

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["provider"] == "codex"
    assert created["packageId"] == "figma-context"

    stale_response = client.put("/api/v1/marketplace/packages/codex/figma-context", json={
        "provider": "codex",
        "packageId": "figma-context",
        "revision": "stale",
        "manifest": {
            "name": "figma-context",
            "version": "0.2.0",
            "description": "Updated package",
        },
    })
    assert stale_response.status_code == 409

    save_response = client.put("/api/v1/marketplace/packages/codex/figma-context", json={
        "provider": "codex",
        "packageId": "figma-context",
        "revision": created["revision"],
        "listing": {
            "name": "figma-context",
            "source": {"source": "local", "path": "./plugins/figma-context"},
            "owner": {"name": "Should Strip"},
            "description": "Should Strip",
        },
        "manifest": {
            "name": "figma-context",
            "version": "0.2.0",
            "description": "Updated package",
        },
        "readmeMarkdown": "# Updated Figma Context\n",
        "packageFiles": [
            {
                "path": ".codex-plugin/plugin.json",
                "content": json.dumps({
                    "name": "figma-context",
                    "version": "0.2.0",
                    "description": "Updated package",
                }),
                "binary": False,
                "size": 87,
            },
            {
                "path": "README.md",
                "content": "# Updated Figma Context\n",
                "binary": False,
                "size": 24,
            },
            {
                "path": ".mcp.json",
                "content": json.dumps({
                    "mcpServers": {
                        "figma": {
                            "command": "npx",
                            "args": ["figma-developer-mcp", "--stdio"],
                        },
                    },
                }),
                "binary": False,
                "size": 91,
            },
        ],
    })

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["package"]["manifestMetadata"]["version"] == "0.2.0"
    assert any(file["path"] == ".mcp.json" for file in saved["package"]["packageFiles"])
    assert saved["validationResults"][0]["messageKey"] == "marketplace.validation.root_metadata_stripped"

    export_response = client.get("/api/v1/marketplace/packages/codex/figma-context/export")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/zip"

    delete_response = client.delete(
        "/api/v1/marketplace/packages/codex/figma-context",
        params={"revision": saved["revision"]},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    activity_response = client.get("/api/v1/marketplace/activity")
    assert activity_response.status_code == 200
    activity = activity_response.json()
    assert activity["total"] == 1
    assert activity["items"][0]["action"] == "delete"
    assert activity["items"][0]["provider"] == "codex"
    assert activity["items"][0]["packageId"] == "figma-context"
    assert activity["items"][0]["status"] == "success"

    detail_response = client.get("/api/v1/marketplace/packages/codex/figma-context")
    assert detail_response.status_code == 404


def test_marketplace_package_save_returns_localized_validation_detail(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Figma Context",
        "description": "Figma MCP package",
    })
    created = create_response.json()

    save_response = client.put("/api/v1/marketplace/packages/codex/figma-context", json={
        "provider": "codex",
        "packageId": "figma-context",
        "revision": created["revision"],
        "manifest": {
            "name": "wrong-id",
            "version": "0.2.0",
        },
    })

    assert save_response.status_code == 400
    body = save_response.json()["detail"]
    assert body["code"] == "marketplace.validation.invalid_manifest_shape"
    assert body["message"]
    assert [result["code"] for result in body["validationResults"]] == [
        "marketplace.validation.invalid_manifest_shape",
        "marketplace.validation.package_identity_mismatch",
    ]


def test_marketplace_package_export_returns_validation_blocking_detail(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/init")
    root = Path(init_response.json()["rootPath"])
    manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plugins"] = [{
        "name": "broken-plugin",
        "source": {"source": "local", "path": "./plugins/broken-plugin"},
    }]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (root / "codex" / "plugins" / "broken-plugin").mkdir(parents=True)

    export_response = client.get("/api/v1/marketplace/packages/codex/broken-plugin/export")

    assert export_response.status_code == 400
    body = export_response.json()["detail"]
    assert body["code"] == "marketplace.validation.required_manifest_missing"
    assert body["message"]
    assert body["validationResults"][0]["severity"] == "error"


def test_marketplace_install_endpoint_validates_revision_and_runtime(test_app, create_user, monkeypatch):
    client, session_factory = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    user = create_user(id="local-user", username="local-user", email="local-user@example.local")
    runtime_payloads = []

    class RuntimeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            argv = self.payload["argv"]
            if argv == ["sh", "-lc", "command -v codex"]:
                return {"status": "success", "stdout": "/home/developer/.npm-global/bin/codex\n", "stderr": ""}
            if argv == ["/home/developer/.npm-global/bin/codex", "--version"]:
                return {"status": "success", "stdout": "codex 1.0.0\n", "stderr": ""}
            if argv == ["/home/developer/.npm-global/bin/codex", "plugin", "marketplace", "--help"]:
                return {"status": "success", "stdout": "Usage: codex plugin marketplace add [--user]\n", "stderr": ""}
            return {
                "status": "success",
                "exitCode": 0,
                "startedAt": "2026-05-07T00:00:00Z",
                "completedAt": "2026-05-07T00:00:01Z",
                "stdout": "installed",
                "stderr": "",
                "truncated": False,
            }

    class RuntimeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *, json, headers):
            runtime_payloads.append({"url": url, "payload": json, "headers": headers})
            return RuntimeResponse(json)

    monkeypatch.setattr("app.services.marketplace_service.httpx.Client", RuntimeClient)
    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Figma Context",
        "description": "Figma MCP package",
    })
    created = create_response.json()

    stale_response = client.post("/api/v1/marketplace/install", json={
        "provider": "codex",
        "packageId": "figma-context",
        "revision": "stale",
        "workspaceId": "workspace-1",
    })
    missing_workspace_response = client.post("/api/v1/marketplace/install", json={
        "provider": "codex",
        "packageId": "figma-context",
        "revision": created["revision"],
        "workspaceId": "workspace-1",
    })

    with session_factory() as session:
        session.add(db_models.Workspace(
            id="workspace-1",
            owner_id=user.id,
            name="Workspace 1",
            runtime_status="running",
            runtime_internal_url="http://workspace-runtime:3002",
        ))
        session.commit()

    install_response = client.post("/api/v1/marketplace/install", json={
        "provider": "codex",
        "packageId": "figma-context",
        "revision": created["revision"],
        "workspaceId": "workspace-1",
    })
    activity_response = client.get("/api/v1/marketplace/activity")
    root = _marketplace_registry_root()
    intents = (root / ".marketplace" / "install-intents.jsonl").read_text(encoding="utf-8").splitlines()

    assert stale_response.status_code == 409
    assert missing_workspace_response.status_code == 200
    assert missing_workspace_response.json()["status"] == "runtimeUnavailable"
    assert missing_workspace_response.json()["errorCode"] == "marketplace.install.workspace_not_found"
    assert install_response.status_code == 200
    assert install_response.json()["status"] == "success"
    assert install_response.json()["errorCode"] is None
    assert len(intents) == 1
    assert json.loads(intents[0])["revision"] == created["revision"]
    assert len(runtime_payloads) == 4
    install_payload = runtime_payloads[-1]["payload"]
    assert runtime_payloads[-1]["url"] == "http://workspace-runtime:3002/api/v1/internal/marketplace/install/execute"
    assert runtime_payloads[-1]["headers"] == {"Authorization": "Bearer dev-internal-token"}
    assert install_payload["provider"] == "codex"
    assert install_payload["argv"] == [
        "/home/developer/.npm-global/bin/codex",
        "plugin",
        "marketplace",
        "add",
        "/marketplace-install/codex",
        "--user",
    ]
    assert install_payload["cwd"] == "/marketplace-install/codex"
    assert install_payload["env"] == {"WORKSPACE_ID": "workspace-1"}
    assert activity_response.status_code == 200
    assert activity_response.json()["items"][0]["action"] == "install"
    assert activity_response.json()["items"][0]["status"] == "success"


def test_marketplace_install_preflight_endpoint_reports_cli_state(test_app, monkeypatch):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    monkeypatch.setattr("app.services.marketplace_service.shutil.which", lambda name: None)

    response = client.get("/api/v1/marketplace/install/preflight", params={"provider": "codex"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "codex"
    assert body["available"] is False
    assert body["errorCode"] == "marketplace.install.cli_unavailable"


def test_marketplace_install_preflight_endpoint_reports_capabilities(test_app, monkeypatch):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    monkeypatch.setattr("app.services.marketplace_service.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="gemini 0.4.0", stderr="")
        return SimpleNamespace(returncode=0, stdout="gemini extensions install --user", stderr="")

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    response = client.get("/api/v1/marketplace/install/preflight", params={"provider": "gemini"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "gemini"
    assert body["available"] is True
    assert body["executablePath"] == "/usr/bin/gemini"
    assert body["version"] == "0.4.0"
    assert body["errorCode"] is None
    assert body["capabilities"]["supportsUserScope"] is True
    assert body["capabilities"]["supportsMarketplaceAdd"] is False
    assert body["capabilities"]["supportsExtensionInstall"] is True


def test_marketplace_install_preflight_endpoint_rejects_invalid_provider(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    response = client.get("/api/v1/marketplace/install/preflight", params={"provider": "invalid-provider"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Marketplace provider"


def test_marketplace_does_not_expose_uninstall_endpoint(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    response = client.post("/api/v1/marketplace/uninstall", json={
        "provider": "codex",
        "packageId": "figma-context",
        "workspaceId": "workspace-1",
    })

    assert response.status_code == 404


def _marketplace_client_with_roles(
    test_app: tuple[TestClient, sessionmaker[Session]],
    create_user,
    monkeypatch,
    *,
    roles: list[str],
    user_id: str,
) -> TestClient:
    client, _ = test_app
    user = create_user(id=user_id, username=user_id, email=f"{user_id}@example.local")

    async def mock_validate_token(self, token: str) -> dict[str, object]:
        return {
            "sub": f"keycloak-{user_id}",
            "preferred_username": user.username,
            "email": user.email,
            "roles": roles,
            "realm_access": {"roles": roles},
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )
    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": f"Bearer token-{user_id}"})
    return client


def test_marketplace_rbac_allows_viewer_read_and_blocks_edit(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["viewer"],
        user_id="marketplace-viewer",
    )

    list_response = client.get("/api/v1/marketplace/packages")
    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Figma Context",
        "description": "Figma MCP package",
    })
    settings_response = client.get("/api/v1/marketplace/settings")
    init_response = client.post("/api/v1/marketplace/registry/init")
    repository_response = client.get("/api/v1/marketplace/registry/repository")
    registry_status_response = client.get("/api/v1/marketplace/registry/status")
    registry_commits_response = client.get("/api/v1/marketplace/registry/commits")
    ssh_key_response = client.get("/api/v1/marketplace/registry/ssh-key")
    settings_save_response = client.put("/api/v1/marketplace/settings", json={
        "name": "Viewer Registry",
        "owner": {
            "name": "Viewer",
            "email": "viewer@example.local",
        },
        "description": "Viewer should not save settings",
    })
    activity_response = client.get("/api/v1/marketplace/activity")
    import_scan_response = client.post("/api/v1/marketplace/import/scan", json={
        "provider": "codex",
        "sourceKind": "git",
        "source": "https://example.com/org/repo.git",
    })
    install_response = client.post("/api/v1/marketplace/install", json={
        "provider": "codex",
        "packageId": "figma-context",
        "revision": "rev",
        "workspaceId": "workspace-1",
    })

    assert list_response.status_code == 200
    assert create_response.status_code == 403
    assert settings_response.status_code == 200
    assert init_response.status_code == 201
    assert repository_response.status_code == 200
    assert registry_status_response.status_code == 200
    assert registry_commits_response.status_code == 200
    assert ssh_key_response.status_code == 200
    assert settings_save_response.status_code == 403
    assert activity_response.status_code == 403
    assert import_scan_response.status_code == 403
    assert install_response.status_code == 403
    assert create_response.json()["detail"] == "You do not have permission to use this Marketplace action"


def test_marketplace_registry_root_is_shared_across_authenticated_users(
    test_app,
    create_user,
    monkeypatch,
):
    admin_client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-shared-admin",
    )
    init_response = admin_client.post("/api/v1/marketplace/registry/init")
    admin_settings_response = admin_client.get("/api/v1/marketplace/settings")

    viewer_client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["viewer"],
        user_id="marketplace-shared-viewer",
    )
    viewer_settings_response = viewer_client.get("/api/v1/marketplace/settings")

    assert init_response.status_code == 201
    assert admin_settings_response.status_code == 200
    assert viewer_settings_response.status_code == 200
    assert init_response.json()["rootPath"] == str(_marketplace_registry_root())
    assert admin_settings_response.json()["rootPath"] == init_response.json()["rootPath"]
    assert viewer_settings_response.json()["rootPath"] == init_response.json()["rootPath"]
    assert "/users/" not in init_response.json()["rootPath"]


def test_marketplace_rbac_accepts_keycloak_realm_roles_when_roles_claim_is_null(
    test_app,
    create_user,
    monkeypatch,
):
    client, _ = test_app
    user_id = "marketplace-realm-role-user"
    user = create_user(id=user_id, username=user_id, email=f"{user_id}@example.local")

    async def mock_validate_token(self, token: str) -> dict[str, object]:
        return {
            "sub": f"keycloak-{user_id}",
            "preferred_username": user.username,
            "email": user.email,
            "roles": None,
            "realm_access": {"roles": ["user"]},
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )
    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": f"Bearer token-{user_id}"})

    list_response = client.get("/api/v1/marketplace/packages")
    settings_response = client.get("/api/v1/marketplace/settings")
    import_scan_response = client.post("/api/v1/marketplace/import/scan", json={
        "provider": "codex",
        "sourceKind": "git",
        "source": "https://token@example.com/org/repo.git",
    })

    assert list_response.status_code == 200
    assert settings_response.status_code == 200
    assert import_scan_response.status_code == 400
    assert import_scan_response.json()["detail"]["code"] == "marketplace.import.validation.https_token_unsupported"


def test_marketplace_rbac_accepts_direct_marketplace_view_permission_claim(
    test_app,
    create_user,
    monkeypatch,
):
    client, _ = test_app
    user_id = "marketplace-permission-claim-user"
    user = create_user(id=user_id, username=user_id, email=f"{user_id}@example.local")

    async def mock_validate_token(self, token: str) -> dict[str, object]:
        return {
            "sub": f"keycloak-{user_id}",
            "preferred_username": user.username,
            "email": user.email,
            "roles": ["viewer"],
            "permissions": ["marketplace.view"],
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )
    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": f"Bearer token-{user_id}"})

    root = _marketplace_registry_root()
    manifest_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({
            "name": "Test Marketplace",
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
            }],
        }),
        encoding="utf-8",
    )
    package_path = root / "codex" / "plugins" / "figma-context" / ".codex-plugin"
    package_path.mkdir(parents=True, exist_ok=True)
    (package_path / "plugin.json").write_text(
        json.dumps({"name": "figma-context", "version": "0.1.0"}),
        encoding="utf-8",
    )

    client.headers.update({"Authorization": f"Bearer token-{user_id}"})
    detail_response = client.get("/api/v1/marketplace/packages/codex/figma-context")
    create_denied_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "denied-package",
        "displayName": "Denied Package",
        "description": "Should not create",
    })

    assert detail_response.status_code == 200
    assert detail_response.json()["packageId"] == "figma-context"
    assert create_denied_response.status_code == 403


def test_marketplace_rbac_accepts_keycloak_authorization_permissions(
    test_app,
    create_user,
    monkeypatch,
):
    client, _ = test_app
    user_id = "marketplace-authz-permission-user"
    user = create_user(id=user_id, username=user_id, email=f"{user_id}@example.local")

    async def mock_validate_token(self, token: str) -> dict[str, object]:
        return {
            "sub": f"keycloak-{user_id}",
            "preferred_username": user.username,
            "email": user.email,
            "roles": ["viewer"],
            "authorization": {
                "permissions": [
                    {"rsname": "marketplace", "scopes": ["view", "edit"]},
                ],
            },
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )
    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": f"Bearer token-{user_id}"})

    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "authz-package",
        "displayName": "Authz Package",
        "description": "Created through authorization permissions",
    })
    delete_response = client.delete(
        "/api/v1/marketplace/packages/codex/authz-package",
        params={"revision": create_response.json()["revision"]},
    )

    assert create_response.status_code == 201
    assert delete_response.status_code == 403


def test_marketplace_rbac_accepts_keycloak_group_mapping(
    test_app,
    create_user,
    monkeypatch,
):
    client, _ = test_app
    user_id = "marketplace-group-user"
    user = create_user(id=user_id, username=user_id, email=f"{user_id}@example.local")

    async def mock_validate_token(self, token: str) -> dict[str, object]:
        return {
            "sub": f"keycloak-{user_id}",
            "preferred_username": user.username,
            "email": user.email,
            "roles": [],
            "groups": ["/developers"],
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )
    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": f"Bearer token-{user_id}"})

    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "group-package",
        "displayName": "Group Package",
        "description": "Created through group mapping",
    })

    assert create_response.status_code == 201


def test_marketplace_rbac_falls_back_to_default_permissions_for_unmapped_keycloak_roles(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["default-roles-aileron", "offline_access", "uma_authorization"],
        user_id="marketplace-default-role-user",
    )

    list_response = client.get("/api/v1/marketplace/packages")
    settings_response = client.get("/api/v1/marketplace/settings")
    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Figma Context",
        "description": "Figma MCP package",
    })
    import_scan_response = client.post("/api/v1/marketplace/import/scan", json={
        "provider": "codex",
        "sourceKind": "git",
        "source": "https://token@example.com/org/repo.git",
    })

    assert list_response.status_code == 200
    assert settings_response.status_code == 200
    assert create_response.status_code == 201
    assert import_scan_response.status_code == 400
    assert import_scan_response.json()["detail"]["code"] == "marketplace.import.validation.https_token_unsupported"


def test_marketplace_rbac_allows_developer_edit_but_blocks_delete_and_registry_management(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["developer"],
        user_id="marketplace-developer",
    )

    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Figma Context",
        "description": "Figma MCP package",
    })
    delete_response = client.delete(
        "/api/v1/marketplace/packages/codex/figma-context",
        params={"revision": create_response.json()["revision"]},
    )
    registry_response = client.post("/api/v1/marketplace/registry/init")
    registry_git_response = client.post("/api/v1/marketplace/registry/git/init")

    assert create_response.status_code == 201
    assert delete_response.status_code == 403
    assert registry_response.status_code == 201
    assert registry_git_response.status_code == 403


def test_marketplace_import_scan_validates_source_inputs(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["developer"],
        user_id="marketplace-importer",
    )

    token_response = client.post("/api/v1/marketplace/import/scan", json={
        "provider": "codex",
        "sourceKind": "git",
        "source": "https://token@example.com/org/repo.git",
    })
    def fake_run(command, **kwargs):
        Path(command[-1]).mkdir(parents=True)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.marketplace_service.subprocess.run", fake_run)

    valid_response = client.post("/api/v1/marketplace/import/scan", json={
        "provider": "codex",
        "sourceKind": "git",
        "source": "https://example.com/org/repo.git",
    })

    assert token_response.status_code == 400
    assert token_response.json()["detail"]["code"] == "marketplace.import.validation.https_token_unsupported"
    assert valid_response.status_code == 200
    assert valid_response.json() == []


def test_marketplace_import_upload_accepts_local_zip_source(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
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

    upload_response = client.post(
        "/api/v1/marketplace/import/upload",
        data={"provider": "codex"},
        files={"file": ("marketplace.zip", buffer.getvalue(), "application/zip")},
    )

    assert upload_response.status_code == 200
    body = upload_response.json()
    assert body["fileName"] == "marketplace.zip"
    assert body["source"]["provider"] == "codex"
    assert body["source"]["sourceKind"] == "local"
    scan_response = client.post("/api/v1/marketplace/import/scan", json=body["source"])
    assert scan_response.status_code == 200
    assert scan_response.json()[0]["packageId"] == "uploaded-plugin"


def test_marketplace_import_endpoint_copies_selected_candidates(test_app):
    client, _ = test_app
    client.headers.update({"X-Internal-Token": "test-internal-token"})
    init_response = client.post("/api/v1/marketplace/registry/init")
    root = Path(init_response.json()["rootPath"])
    source_root = root.parent / "import-sources" / "codex-api-import"
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
            "description": "Figma context package",
        }),
        encoding="utf-8",
    )
    source_payload = {
        "provider": "codex",
        "sourceKind": "local",
        "source": str(source_root),
    }

    scan_response = client.post("/api/v1/marketplace/import/scan", json=source_payload)
    import_response = client.post("/api/v1/marketplace/import", json={
        "source": source_payload,
        "candidates": scan_response.json(),
    })

    assert scan_response.status_code == 200
    assert import_response.status_code == 200
    body = import_response.json()
    assert body["imported"][0]["packageId"] == "figma-context"
    assert body["imported"][0]["sourceType"] == "imported"
    assert body["skipped"] == []
    assert body["failed"] == []
    assert (root / "codex" / "plugins" / "figma-context" / ".codex-plugin" / "plugin.json").exists()

    detail_response = client.get("/api/v1/marketplace/packages/codex/figma-context")
    detail = detail_response.json()
    assert detail_response.status_code == 200
    assert detail["sourceType"] == "imported"
    assert detail["manifestMetadata"]["importSource"]["source"] == str(source_root)
    assert detail["manifestMetadata"]["importSource"]["packageId"] == "figma-context"


def test_marketplace_rbac_allows_admin_registry_management_and_delete(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-admin",
    )

    init_response = client.post("/api/v1/marketplace/registry/init")
    create_response = client.post("/api/v1/marketplace/packages", json={
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Figma Context",
        "description": "Figma MCP package",
    })
    delete_response = client.delete(
        "/api/v1/marketplace/packages/codex/figma-context",
        params={"revision": create_response.json()["revision"]},
    )

    assert init_response.status_code == 201
    assert create_response.status_code == 201
    assert delete_response.status_code == 200
