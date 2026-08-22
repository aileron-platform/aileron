"""Marketplace API tests."""

from __future__ import annotations

import json
import os
import subprocess
import time
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.api_error import authorization_error_detail
from app.db import models as db_models
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.marketplace import router as marketplace_router
from app.modules.marketplace.cli_install import MarketplaceCliInstallError
from tests.helpers.manager_session import authenticate_client_as


def _marketplace_registry_root() -> Path:
    return Path(os.environ["MARKETPLACE_STORAGE_PATH"]) / "registry"


def _replace_catalog_packages(
    root: Path,
    packages: list[dict[str, object]],
) -> None:
    catalog_path = root / "marketplace" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["packages"] = [
        {
            **package,
            "packageFormat": package.get("packageFormat")
            or (
                "claude-native"
                if package["targetClient"] == "claude-code"
                else "codex-native"
            ),
            "userCopyTargetClient": package.get("userCopyTargetClient")
            or package["targetClient"],
            "catalogPluginId": package.get("catalogPluginId")
            or (
                f"{catalog['marketplaceId']}/"
                f"{package.get('packageFormat') or ('claude-native' if package['targetClient'] == 'claude-code' else 'codex-native')}/"
                f"{package['packageId']}"
            ),
        }
        for package in packages
    ]
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")


@pytest.fixture(autouse=True)
def authenticate_marketplace_requests(test_app, create_user) -> None:
    """Use a valid platform-admin principal for Marketplace integration tests."""

    client, session_factory = test_app
    user = create_user(
        id="marketplace-default-admin",
        username="marketplace-default-admin",
        email="marketplace-default-admin@example.local",
        platform_role="admin",
        role_status="valid",
    )
    with session_factory() as session:
        session.add(
            db_models.UserSetting(
                id="marketplace-default-settings",
                user_id=user.id,
                git_user_name="Marketplace Test User",
                git_user_email="marketplace-test@example.local",
            )
        )
        session.commit()

    authenticate_client_as(client, user)


def test_marketplace_registry_init_and_settings_save(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")

    assert response.status_code == 200
    body = response.json()
    root = _marketplace_registry_root()
    assert body["isInitialized"] is True
    assert body["currentBranch"] == "main"
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

    claude = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())
    codex = json.loads((root / ".agents" / "plugins" / "marketplace.json").read_text())
    assert claude["owner"] == {"name": "Team Maintainer", "email": "team@example.local"}
    assert claude["plugins"] == []
    assert codex["name"] == "aileron-internal"
    assert "owner" not in codex
    assert codex["plugins"] == []


def test_marketplace_registry_uses_system_git_identity_for_commit(test_app):
    client, session_factory = test_app
    client.post("/api/v1/marketplace/version-control/init")

    with session_factory() as session:
        settings = session.get(
            db_models.UserSetting,
            "marketplace-default-settings",
        )
        assert settings is not None
        settings.git_user_name = "System Settings User"
        settings.git_user_email = "system-settings@example.local"
        session.commit()

    root = _marketplace_registry_root()
    manifest = root / ".agents" / "plugins" / "marketplace.json"
    manifest.write_text(
        json.dumps({"name": "Identity Check", "plugins": []}),
        encoding="utf-8",
    )
    stage_response = client.post(
        "/api/v1/marketplace/version-control/stage",
        json={"paths": [".agents/plugins/marketplace.json"]},
    )
    commit_response = client.post(
        "/api/v1/marketplace/version-control/commit",
        json={"message": "Use system identity"},
    )

    assert stage_response.status_code == 200
    assert commit_response.status_code == 200
    author = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae>"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert author.stdout.strip() == (
        "System Settings User <system-settings@example.local>"
    )


def test_marketplace_registry_rejects_commit_path_override(test_app):
    client, _ = test_app
    client.post("/api/v1/marketplace/version-control/init")

    response = client.post(
        "/api/v1/marketplace/version-control/commit",
        json={"message": "Invalid path override", "paths": ["README.md"]},
    )

    assert response.status_code == 422


def test_marketplace_branch_routes_share_safe_local_branch_semantics(test_app):
    client, _ = test_app
    assert client.post("/api/v1/marketplace/version-control/init").status_code == 200
    assert (
        client.post(
            "/api/v1/marketplace/version-control/stage",
            json={"all": True},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/marketplace/version-control/commit",
            json={"message": "Initialize registry"},
        ).status_code
        == 200
    )

    created = client.post(
        "/api/v1/marketplace/version-control/branches/create",
        json={"name": "feature", "startPoint": "HEAD"},
    )
    renamed = client.post(
        "/api/v1/marketplace/version-control/branches/rename",
        json={"oldName": "feature", "newName": "renamed"},
    )
    switched = client.post(
        "/api/v1/marketplace/version-control/branches/switch",
        json={"name": "main"},
    )
    deleted = client.post(
        "/api/v1/marketplace/version-control/branches/delete",
        json={"name": "renamed"},
    )
    branches = client.get("/api/v1/marketplace/version-control/branches")

    assert created.status_code == 200
    assert created.json()["branch"] == "feature"
    assert renamed.status_code == 200
    assert renamed.json()["branch"] == "renamed"
    assert switched.status_code == 200
    assert deleted.status_code == 200
    assert branches.status_code == 200
    assert [branch["name"] for branch in branches.json()["branches"]] == ["main"]


def test_marketplace_lfs_patterns_use_shared_repository_contract(test_app, monkeypatch):
    client, _ = test_app
    assert client.post("/api/v1/marketplace/version-control/init").status_code == 200
    root = _marketplace_registry_root()
    asset = root / "asset.bin"
    asset.write_bytes(b"snapshot")
    (root / ".gitattributes").write_text(
        "# keep this comment\n*.txt text eol=lf\n",
        encoding="utf-8",
    )

    response = client.post(
        "/api/v1/marketplace/version-control/lfs",
        json={"patterns": ["*.bin", "*.bin"]},
    )

    assert response.status_code == 200
    attributes = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "# keep this comment\n" in attributes
    assert "*.txt text eol=lf\n" in attributes
    assert "*.bin filter=lfs diff=lfs merge=lfs -text\n" in attributes
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert ".gitattributes" in staged.stdout.splitlines()
    patterns_response = client.get("/api/v1/marketplace/version-control/lfs")
    preview_response = client.post(
        "/api/v1/marketplace/version-control/lfs/preview",
        json={},
    )
    monkeypatch.setattr(
        "aileron_git_core.application.convert_snapshot",
        lambda _root, paths, **_kwargs: tuple(paths),
    )
    convert_response = client.post(
        "/api/v1/marketplace/version-control/lfs/convert",
        json={"paths": ["asset.bin"]},
    )
    cancel_response = client.post(
        "/api/v1/marketplace/version-control/operation/cancel"
    )

    assert patterns_response.status_code == 200
    assert patterns_response.json() == {"patterns": ["*.bin"]}
    assert preview_response.status_code == 200
    assert preview_response.json() == {
        "matchedTotal": 1,
        "totalSize": len(b"snapshot"),
        "pathSample": ["asset.bin"],
    }
    assert convert_response.status_code == 200
    assert convert_response.json()["commandId"] == "lfs.snapshot.convert"
    assert convert_response.json()["affectedTotal"] == 1
    assert cancel_response.status_code == 409
    assert cancel_response.json()["detail"]["errorCode"] == "operation_not_cancellable"
    assert (
        client.post(
            "/api/v1/marketplace/version-control/lfs/preview",
            json={"extra": True},
        ).status_code
        == 422
    )


def test_marketplace_package_list_and_detail_scan_registry(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200
    root = _marketplace_registry_root()
    _replace_catalog_packages(
        root,
        [
            {
                "targetClient": "codex",
                "packageId": "figma-context",
                "category": "design",
                "tags": ["mcp"],
            }
        ],
    )
    package_root = root / "codex" / "plugins" / "codex-native" / "figma-context"
    (package_root / ".codex-plugin").mkdir(parents=True)
    (package_root / "skills" / "review").mkdir(parents=True)
    (package_root / "skills" / "review" / "SKILL.md").write_text(
        "# Review\n", encoding="utf-8"
    )
    (package_root / "README.md").write_text("# Figma Context\n", encoding="utf-8")
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "figma-context",
                "version": "0.2.0",
                "description": "Figma MCP package",
            }
        ),
        encoding="utf-8",
    )
    (package_root / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"figma": {"command": "node"}}}),
        encoding="utf-8",
    )

    list_response = client.get(
        "/api/v1/marketplace/packages?target_client=codex&features=skills"
    )

    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["items"][0]["packageId"] == "figma-context"
    assert listed["items"][0]["validationSeverity"] == "none"

    detail_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native"
    )

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["manifestMetadata"]["version"] == "0.2.0"
    assert "readmeMarkdown" not in detail
    assert "featureContent" not in detail
    assert "packageFiles" not in detail

    readme_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context/readme?packageFormat=codex-native"
    )
    skills_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context/skills/tree?packageFormat=codex-native"
    )
    mcp_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context/mcp-servers?packageFormat=codex-native"
    )
    assert readme_response.json()["content"] == "# Figma Context\n"
    assert skills_response.json()["nodes"][0]["path"] == "skills/review"
    assert mcp_response.json()[0]["name"] == "figma"
    assert "server" not in mcp_response.json()[0]


def test_same_target_package_formats_are_addressed_as_distinct_variants(test_app):
    client, _ = test_app
    assert client.post("/api/v1/marketplace/version-control/init").status_code == 200
    root = _marketplace_registry_root()
    _replace_catalog_packages(
        root,
        [
            {
                "targetClient": "codex",
                "packageFormat": "codex-native",
                "packageId": "shared-name",
            },
            {
                "targetClient": "codex",
                "packageFormat": "agent-plugin/1.0.0",
                "packageId": "shared-name",
            },
        ],
    )
    native = root / "codex" / "plugins" / "codex-native" / "shared-name"
    portable = root / "codex" / "plugins" / "agent-plugin-1.0.0" / "shared-name"
    (native / ".codex-plugin").mkdir(parents=True)
    (native / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "shared-name",
                "version": "1.0.0",
                "description": "Native build",
            }
        ),
        encoding="utf-8",
    )
    portable.mkdir(parents=True)
    (portable / "plugin.json").write_text(
        json.dumps(
            {
                "$schema": (
                    "https://agent-plugins.org/schemas/1.0.0/" "plugin.schema.json"
                ),
                "name": "shared-name",
                "version": "2.0.0",
                "description": "Portable build",
            }
        ),
        encoding="utf-8",
    )

    native_response = client.get(
        "/api/v1/marketplace/packages/codex/shared-name",
        params={"packageFormat": "codex-native"},
    )
    portable_response = client.get(
        "/api/v1/marketplace/packages/codex/shared-name",
        params={"packageFormat": "agent-plugin/1.0.0"},
    )
    missing_format = client.get("/api/v1/marketplace/packages/codex/shared-name")

    assert native_response.status_code == 200
    assert native_response.json()["packageFormat"] == "codex-native"
    assert native_response.json()["version"] == "1.0.0"
    assert portable_response.status_code == 200
    assert portable_response.json()["packageFormat"] == "agent-plugin/1.0.0"
    assert portable_response.json()["version"] == "2.0.0"
    assert missing_format.status_code == 400


def test_marketplace_package_refresh_endpoint_returns_registry_fingerprint(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200
    root = _marketplace_registry_root()
    _replace_catalog_packages(
        root,
        [{"targetClient": "codex", "packageId": "figma-context"}],
    )
    manifest_path = root / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plugins"] = [
        {
            "name": "figma-context",
            "source": {"source": "local", "path": "./plugins/figma-context"},
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    package_root = root / "codex" / "plugins" / "codex-native" / "figma-context"
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


def test_marketplace_package_refresh_endpoint_returns_minimal_result(test_app):
    client, _ = test_app
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "figma-context",
            "displayName": "Figma Context",
            "version": "1.0.0",
            "description": "Figma package",
        },
    )
    assert created.status_code == 201, created.text

    response = client.post(
        "/api/v1/marketplace/packages/codex/figma-context/refresh?packageFormat=codex-native"
    )

    assert response.status_code == 200
    assert response.json() == {"refreshed": True}


def test_marketplace_package_file_conflict_routes_execute_upload_and_paste(test_app):
    client, _ = test_app
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "file-contract",
            "displayName": "File Contract",
            "version": "1.0.0",
            "description": "Shared file contract",
        },
    )
    assert created.status_code == 201
    revision = created.json()["revision"]
    source = client.post(
        "/api/v1/marketplace/packages/codex/file-contract/files?packageFormat=codex-native",
        json={
            "revision": revision,
            "path": "docs/a.txt",
            "type": "file",
            "content": "old",
        },
    )
    assert source.status_code == 200

    preflight = client.post(
        "/api/v1/marketplace/packages/codex/file-contract/files/conflicts/preflight?packageFormat=codex-native",
        json={
            "operation": "paste",
            "targetPath": "copies",
            "sources": [{"sourcePath": "docs/a.txt", "entryType": "file"}],
            "archivePath": None,
        },
    )
    pasted = client.post(
        "/api/v1/marketplace/packages/codex/file-contract/files/paste?packageFormat=codex-native",
        json={
            "targetPath": "copies",
            "sources": [{"sourcePath": "docs/a.txt", "entryType": "file"}],
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )
    uploaded = client.post(
        "/api/v1/marketplace/packages/codex/file-contract/files/upload?packageFormat=codex-native",
        data={
            "targetPath": "docs",
            "defaultStrategy": "keep-both",
            "resolutions": "[]",
        },
        files=[("files", ("a.txt", b"new", "text/plain"))],
    )
    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("inside.txt", "inside")
    archive_upload = client.post(
        "/api/v1/marketplace/packages/codex/file-contract/files/upload?packageFormat=codex-native",
        data={
            "targetPath": "docs",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files=[
            (
                "files",
                ("sample.zip", archive_buffer.getvalue(), "application/zip"),
            )
        ],
    )
    extracted = client.post(
        "/api/v1/marketplace/packages/codex/file-contract/files/extract?packageFormat=codex-native",
        json={
            "archivePath": "docs/sample.zip",
            "targetPath": "extracted",
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )

    assert preflight.status_code == 200
    assert preflight.json() == {"conflicts": [], "total": 1}
    assert pasted.status_code == 200
    assert set(pasted.json()) == {"items", "total", "succeeded", "skipped", "failed"}
    assert set(pasted.json()["items"][0]) == {
        "sourcePath",
        "finalPath",
        "status",
        "size",
        "type",
        "error",
    }
    assert pasted.json()["items"][0]["status"] == "created"
    assert uploaded.status_code == 200
    assert uploaded.json()["items"][0]["status"] == "kept-both"
    assert "uploaded" not in uploaded.json()
    assert "success" not in uploaded.json()
    assert archive_upload.status_code == 200
    assert extracted.status_code == 200
    assert extracted.json()["items"][0]["sourcePath"] == "inside.txt"
    assert extracted.json()["items"][0]["status"] == "created"


def test_marketplace_skill_conflict_routes_are_revision_fenced_and_exact(test_app):
    client, _ = test_app
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "skill-file-contract",
            "displayName": "Skill File Contract",
            "version": "1.0.0",
            "description": "Managed skill file contract",
        },
    )
    assert created.status_code == 201, created.text
    initial_revision = created.json()["revision"]
    skill_base_url = "/api/v1/marketplace/packages/codex/skill-file-contract/skills"

    preflight = client.post(
        f"{skill_base_url}/conflicts/preflight?packageFormat=codex-native",
        json={
            "revision": initial_revision,
            "operation": "upload",
            "targetPath": "skills/demo",
            "sources": [{"sourcePath": "SKILL.md", "entryType": "file"}],
            "archivePath": None,
        },
    )
    assert preflight.status_code == 200, preflight.text
    assert preflight.json() == {"conflicts": [], "total": 1}

    uploaded = client.post(
        f"{skill_base_url}/upload?packageFormat=codex-native",
        data={
            "revision": initial_revision,
            "targetPath": "skills/demo",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files=[("files", ("SKILL.md", b"# Skill", "text/markdown"))],
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json() == {
        "items": [
            {
                "sourcePath": "SKILL.md",
                "finalPath": "skills/demo/SKILL.md",
                "status": "created",
                "size": len(b"# Skill"),
                "type": "file",
                "error": None,
            }
        ],
        "total": 1,
        "succeeded": 1,
        "skipped": 0,
        "failed": 0,
    }
    assert "revision" not in uploaded.json()

    stale_upload = client.post(
        f"{skill_base_url}/upload?packageFormat=codex-native",
        data={
            "revision": initial_revision,
            "targetPath": "skills/demo",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files=[("files", ("README.md", b"stale", "text/markdown"))],
    )
    assert stale_upload.status_code == 409

    after_upload = client.get(
        "/api/v1/marketplace/packages/codex/skill-file-contract?packageFormat=codex-native"
    )
    assert after_upload.status_code == 200
    upload_revision = after_upload.json()["revision"]
    assert upload_revision != initial_revision

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("archived/SKILL.md", "# Archived")
    archive_upload = client.post(
        f"{skill_base_url}/upload?packageFormat=codex-native",
        data={
            "revision": upload_revision,
            "targetPath": "skills",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files=[
            (
                "files",
                ("skills.zip", archive_buffer.getvalue(), "application/zip"),
            )
        ],
    )
    assert archive_upload.status_code == 200, archive_upload.text

    after_archive_upload = client.get(
        "/api/v1/marketplace/packages/codex/skill-file-contract?packageFormat=codex-native"
    )
    archive_revision = after_archive_upload.json()["revision"]
    assert archive_revision != upload_revision
    extract_preflight = client.post(
        f"{skill_base_url}/conflicts/preflight?packageFormat=codex-native",
        json={
            "revision": archive_revision,
            "operation": "extract",
            "targetPath": "skills",
            "sources": None,
            "archivePath": "skills/skills.zip",
        },
    )
    assert extract_preflight.status_code == 200, extract_preflight.text
    assert extract_preflight.json() == {"conflicts": [], "total": 1}

    extracted = client.post(
        f"{skill_base_url}/extract?packageFormat=codex-native",
        json={
            "revision": archive_revision,
            "archivePath": "skills/skills.zip",
            "targetPath": "skills",
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )
    assert extracted.status_code == 200, extracted.text
    assert set(extracted.json()) == {
        "items",
        "total",
        "succeeded",
        "skipped",
        "failed",
    }
    assert extracted.json()["items"][0] == {
        "sourcePath": "archived/SKILL.md",
        "finalPath": "skills/archived/SKILL.md",
        "status": "created",
        "size": len(b"# Archived"),
        "type": "file",
        "error": None,
    }
    assert "revision" not in extracted.json()
    after_extract = client.get(
        "/api/v1/marketplace/packages/codex/skill-file-contract?packageFormat=codex-native"
    )
    assert after_extract.json()["revision"] != archive_revision

    paste_preflight = client.post(
        f"{skill_base_url}/conflicts/preflight?packageFormat=codex-native",
        json={
            "revision": after_extract.json()["revision"],
            "operation": "paste",
            "targetPath": "skills",
            "sources": [{"sourcePath": "skills/demo/SKILL.md", "entryType": "file"}],
            "archivePath": None,
        },
    )
    assert paste_preflight.status_code == 400
    assert (
        client.post(
            f"{skill_base_url}/paste?packageFormat=codex-native", json={}
        ).status_code
        == 404
    )

    openapi_operation = client.get("/openapi.json").json()["paths"][
        "/api/v1/marketplace/packages/{target_client}/{package_id}/skills/upload"
    ]["post"]
    assert "archiveAction" not in json.dumps(openapi_operation)
    assert "keepArchive" not in json.dumps(openapi_operation)


def test_marketplace_registry_git_lifecycle_endpoints(test_app, tmp_path):
    client, _ = test_app
    remote_path = tmp_path / "registry.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    status_response = client.get("/api/v1/marketplace/version-control/repository")
    init_response = client.post(
        "/api/v1/marketplace/version-control/init",
        json={"defaultBranch": "main"},
    )
    remote_response = client.put(
        "/api/v1/marketplace/version-control/remote",
        json={"remoteUrl": str(remote_path)},
    )
    remote_settings_response = client.get("/api/v1/marketplace/version-control/remote")
    assert status_response.status_code == 200
    assert status_response.json()["isGitRepo"] is False
    assert init_response.status_code == 200
    assert init_response.json()["isInitialized"] is True
    assert init_response.json()["currentBranch"] == "main"
    assert init_response.json()["hasOrigin"] is False
    assert remote_response.status_code == 200
    assert remote_response.json()["output"] == "origin"
    assert remote_settings_response.status_code == 200
    assert remote_settings_response.json() == {
        "remoteName": "origin",
        "remoteUrl": str(remote_path),
        "hasOrigin": True,
    }
    assert (
        client.put(
            "/api/v1/marketplace/version-control/remote",
            json={"remoteUrl": str(remote_path), "extra": True},
        ).status_code
        == 422
    )


def test_marketplace_operation_status_reports_inactive_when_idle(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200

    response = client.get("/api/v1/marketplace/version-control/operation-status")

    assert response.status_code == 200
    body = response.json()
    assert body["isActive"] is False
    assert body["operation"] is None


def test_marketplace_registry_status_endpoint_returns_target_client_prefixed_changes(
    test_app,
):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200
    root = _marketplace_registry_root()
    subprocess.run(
        ["git", "add", "."], cwd=root, check=True, capture_output=True, text=True
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.local",
            "commit",
            "-m",
            "Initial registry",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    codex_manifest = root / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps(
            {"name": "Changed Registry", "description": "Changed", "plugins": []}
        ),
        encoding="utf-8",
    )
    readme_path = (
        root
        / "claude-code"
        / "plugins"
        / "claude-native"
        / "review-assistant"
        / "README.md"
    )
    readme_path.parent.mkdir(parents=True)
    readme_path.write_text("# Review\n", encoding="utf-8")
    claude_plugin_path = (
        root
        / "claude-code"
        / "plugins"
        / "claude-native"
        / "review-assistant"
        / ".claude-plugin"
        / "plugin.json"
    )
    claude_plugin_path.parent.mkdir(parents=True)
    claude_plugin_path.write_text(
        json.dumps({"name": "review-assistant"}), encoding="utf-8"
    )
    subprocess.run(
        [
            "git",
            "add",
            "claude-code/plugins/claude-native/review-assistant/.claude-plugin/plugin.json",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    changes_response = client.get("/api/v1/marketplace/version-control/changes")
    status_response = client.get("/api/v1/marketplace/version-control/status")

    assert changes_response.status_code == 200
    assert status_response.status_code == 200
    changes = changes_response.json()
    status = status_response.json()
    assert status["currentBranch"]
    assert [
        (item["path"], item["status"], item["type"])
        for item in changes["staged"]["items"]
    ] == [
        (
            "claude-code/plugins/claude-native/review-assistant/.claude-plugin/plugin.json",
            "A",
            "added",
        )
    ]
    assert changes["unstaged"]["items"][0]["path"] == ".agents/plugins/marketplace.json"
    assert (
        changes["untracked"]["items"][0]["path"]
        == "claude-code/plugins/claude-native/review-assistant/README.md"
    )
    assert changes["staged"]["total"] == 1
    assert status["stagedTotal"] == 1


def test_marketplace_registry_diff_endpoints_return_selected_file_patches(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200
    root = _marketplace_registry_root()
    subprocess.run(
        ["git", "add", "."], cwd=root, check=True, capture_output=True, text=True
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.local",
            "commit",
            "-m",
            "Initial registry",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    codex_manifest = root / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps(
            {"name": "Changed Registry", "description": "Changed", "plugins": []},
            indent=2,
        ),
        encoding="utf-8",
    )

    worktree_response = client.get(
        "/api/v1/marketplace/version-control/diff",
        params={"path": ".agents/plugins/marketplace.json"},
    )
    subprocess.run(
        ["git", "add", ".agents/plugins/marketplace.json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    index_response = client.get(
        "/api/v1/marketplace/version-control/diff",
        params={"path": ".agents/plugins/marketplace.json", "head": "INDEX"},
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.local",
            "commit",
            "-m",
            "Update codex registry",
        ],
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
        f"/api/v1/marketplace/version-control/commits/{commit_id}/diff",
        params={"path": ".agents/plugins/marketplace.json"},
    )
    commit_files_response = client.get(
        f"/api/v1/marketplace/version-control/commits/{commit_id}/files"
    )
    escape_response = client.get(
        "/api/v1/marketplace/version-control/diff", params={"path": "../outside.json"}
    )

    assert worktree_response.status_code == 200
    assert worktree_response.json()["head"] == "WORKTREE"
    assert '+  "name": "Changed Registry"' in worktree_response.json()["patch"]
    assert index_response.status_code == 200
    assert index_response.json()["head"] == "INDEX"
    assert '+  "name": "Changed Registry"' in index_response.json()["patch"]
    assert commit_response.status_code == 200
    assert commit_response.json()["commitId"] == commit_id
    assert '+  "name": "Changed Registry"' in commit_response.json()["patch"]
    assert commit_files_response.status_code == 200
    assert (
        commit_files_response.json()["files"][0]["path"]
        == ".agents/plugins/marketplace.json"
    )
    assert escape_response.status_code == 400


def test_marketplace_registry_history_is_empty_before_the_first_commit(test_app):
    client, _ = test_app
    init_response = client.post("/api/v1/marketplace/version-control/init")
    assert init_response.status_code == 200

    history_response = client.get(
        "/api/v1/marketplace/version-control/commits",
        params={"limit": 50, "queryScope": "current"},
    )

    assert history_response.status_code == 200
    assert history_response.json()["items"] == []
    assert history_response.json()["total"] == 0
    assert history_response.json()["hasMore"] is False
    assert history_response.json()["nextCursor"] is None


def test_marketplace_registry_stage_unstage_commit_and_history_endpoints(test_app):
    client, _ = test_app
    init_response = client.post("/api/v1/marketplace/version-control/init")
    assert init_response.status_code == 200
    root = _marketplace_registry_root()
    empty_response = client.post(
        "/api/v1/marketplace/version-control/commit", json={"message": "Nothing"}
    )
    codex_manifest = root / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps(
            {"name": "Changed Registry", "description": "Changed", "plugins": []},
            indent=2,
        ),
        encoding="utf-8",
    )

    stage_response = client.post(
        "/api/v1/marketplace/version-control/stage",
        json={"paths": [".agents/plugins/marketplace.json"]},
    )
    unstage_response = client.post(
        "/api/v1/marketplace/version-control/unstage",
        json={"paths": [".agents/plugins/marketplace.json"]},
    )
    restage_response = client.post(
        "/api/v1/marketplace/version-control/stage",
        json={"paths": [".agents/plugins/marketplace.json"]},
    )
    commit_response = client.post(
        "/api/v1/marketplace/version-control/commit",
        json={"message": "Update codex registry"},
    )
    history_response = client.get(
        "/api/v1/marketplace/version-control/commits", params={"limit": 10}
    )

    assert empty_response.status_code == 200
    assert empty_response.json()["success"] is False
    assert empty_response.json()["errorCode"] == "marketplace.git.no_changes_to_commit"
    assert stage_response.status_code == 200
    assert stage_response.json()["staged"] == [".agents/plugins/marketplace.json"]
    assert unstage_response.status_code == 200
    assert unstage_response.json()["unstaged"] == [".agents/plugins/marketplace.json"]
    assert unstage_response.json()["remainingStaged"] == 0
    assert restage_response.status_code == 200
    assert commit_response.status_code == 200
    assert commit_response.json()["success"] is True
    assert commit_response.json()["commit"]["message"] == "Update codex registry"
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
    assert (
        history_response.json()["items"][0]["id"]
        == commit_response.json()["commit"]["id"]
    )


def test_marketplace_registry_remote_sync_endpoints(test_app, tmp_path):
    client, _ = test_app
    remote = tmp_path / "registry.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    init_response = client.post(
        "/api/v1/marketplace/version-control/init", json={"defaultBranch": "main"}
    )
    assert init_response.status_code == 200
    assert (
        client.put(
            "/api/v1/marketplace/version-control/remote",
            json={"remoteUrl": str(remote)},
        ).status_code
        == 200
    )
    root = _marketplace_registry_root()
    codex_manifest = root / ".agents" / "plugins" / "marketplace.json"
    codex_manifest.write_text(
        json.dumps(
            {"name": "Changed Registry", "description": "Changed", "plugins": []},
            indent=2,
        ),
        encoding="utf-8",
    )
    assert (
        client.post(
            "/api/v1/marketplace/version-control/stage",
            json={"all": True},
        ).status_code
        == 200
    )
    commit_response = client.post(
        "/api/v1/marketplace/version-control/commit",
        json={"message": "Initial registry"},
    )
    push_response = client.post("/api/v1/marketplace/version-control/push")
    peer = tmp_path / "peer"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote), str(peer)],
        check=True,
        capture_output=True,
        text=True,
    )
    (peer / "REMOTE.md").write_text("# Remote\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "REMOTE.md"],
        cwd=peer,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Peer",
            "-c",
            "user.email=peer@example.local",
            "commit",
            "-m",
            "Remote update",
        ],
        cwd=peer,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "push", "origin", "HEAD"],
        cwd=peer,
        check=True,
        capture_output=True,
        text=True,
    )

    fetch_response = client.post("/api/v1/marketplace/version-control/fetch")
    pull_response = client.post("/api/v1/marketplace/version-control/pull")

    assert commit_response.status_code == 200
    assert commit_response.json()["success"] is True
    assert push_response.status_code == 200
    assert push_response.json()["messageKey"] == "marketplace.git.push_success"
    assert fetch_response.status_code == 200
    assert fetch_response.json()["messageKey"] == "marketplace.git.fetch_success"
    assert pull_response.status_code == 200, pull_response.text
    assert pull_response.json()["messageKey"] == "marketplace.git.pull_success"
    assert (root / "REMOTE.md").read_text(encoding="utf-8") == "# Remote\n"


def test_marketplace_package_list_endpoint_applies_filters_and_pagination(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200
    root = _marketplace_registry_root()
    _replace_catalog_packages(
        root,
        [
            {
                "targetClient": "claude-code",
                "packageId": "review-assistant",
                "category": "quality",
                "tags": ["review", "skills"],
            },
            {
                "targetClient": "codex",
                "packageId": "figma-context",
                "category": "design",
                "tags": ["mcp", "commands"],
            },
        ],
    )
    claude_package = (
        root / "claude-code" / "plugins" / "claude-native" / "review-assistant"
    )
    codex_package = root / "codex" / "plugins" / "codex-native" / "figma-context"
    (claude_package / ".claude-plugin").mkdir(parents=True)
    (codex_package / ".codex-plugin").mkdir(parents=True)
    (claude_package / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "review-assistant", "version": "1.0.0"}),
        encoding="utf-8",
    )
    (codex_package / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "figma-context",
                "version": "1.0.0",
                "description": "Figma MCP package",
            }
        ),
        encoding="utf-8",
    )

    paged_response = client.get("/api/v1/marketplace/packages", params={"pageSize": 1})
    target_client_response = client.get(
        "/api/v1/marketplace/packages", params={"target_client": "codex"}
    )
    category_response = client.get(
        "/api/v1/marketplace/packages", params={"category": "quality"}
    )
    feature_response = client.get(
        "/api/v1/marketplace/packages", params={"features": "commands"}
    )
    query_response = client.get("/api/v1/marketplace/packages", params={"q": "review"})

    assert paged_response.status_code == 200
    paged = paged_response.json()
    assert paged["total"] == 2
    assert paged["pageSize"] == 1
    assert paged["totalPages"] == 2
    assert paged["categories"] == ["design", "quality"]
    assert paged["validationSeverities"] == ["none"]
    assert [item["packageId"] for item in target_client_response.json()["items"]] == [
        "figma-context"
    ]
    assert [item["packageId"] for item in category_response.json()["items"]] == [
        "review-assistant"
    ]
    assert [item["packageId"] for item in feature_response.json()["items"]] == [
        "figma-context"
    ]
    assert [item["packageId"] for item in query_response.json()["items"]] == [
        "review-assistant"
    ]


def test_marketplace_package_create_save_delete_and_export(test_app):
    client, _ = test_app

    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "figma-context",
            "displayName": "Figma Context",
            "version": "1.0.0",
            "description": "Figma MCP package",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["targetClient"] == "codex"
    assert created["packageId"] == "figma-context"

    stale_response = client.put(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native",
        json={
            "targetClient": "codex",
            "packageId": "figma-context",
            "revision": "stale",
            "manifest": {
                "name": "figma-context",
                "version": "0.2.0",
                "description": "Updated package",
            },
            "packageFiles": [],
        },
    )
    assert stale_response.status_code == 409

    save_response = client.put(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native",
        json={
            "targetClient": "codex",
            "packageId": "figma-context",
            "revision": created["revision"],
            "listing": {
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
                "owner": {"name": "Should Strip"},
                "description": "Catalog description",
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
                    "content": json.dumps(
                        {
                            "name": "figma-context",
                            "version": "0.2.0",
                            "description": "Updated package",
                        }
                    ),
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
                    "content": json.dumps(
                        {
                            "mcpServers": {
                                "figma": {
                                    "command": "npx",
                                    "args": ["figma-developer-mcp", "--stdio"],
                                },
                            },
                        }
                    ),
                    "binary": False,
                    "size": 91,
                },
            ],
        },
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved == {
        "success": True,
        "path": ".codex-plugin/plugin.json",
        "revision": saved["revision"],
        "ownerFilePath": None,
        "baseEntryFingerprint": None,
    }
    assert saved["revision"] != created["revision"]
    detail_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native"
    )
    files_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context/files/tree?packageFormat=codex-native"
    )
    assert detail_response.json()["manifestMetadata"]["version"] == "0.2.0"
    assert any(item["path"] == ".mcp.json" for item in files_response.json()["nodes"])
    stale_export_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context/export?packageFormat=codex-native",
        params={"packageFormat": "codex-native", "revision": "stale"},
    )
    assert stale_export_response.status_code == 409

    export_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context/export?packageFormat=codex-native",
        params={"packageFormat": "codex-native"},
    )
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(export_response.content)) as archive:
        assert ".agents/plugins/marketplace.json" in archive.namelist()
        assert (
            "codex/plugins/codex-native/figma-context/" ".codex-plugin/plugin.json"
        ) in archive.namelist()

    delete_response = client.delete(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native",
        params={
            "packageFormat": "codex-native",
            "revision": detail_response.json()["revision"],
        },
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    activity_response = client.get("/api/v1/marketplace/activities")
    assert activity_response.status_code == 200
    activity = activity_response.json()
    assert activity["total"] == 1
    assert activity["items"][0]["action"] == "delete"
    assert activity["items"][0]["targetClient"] == "codex"
    assert activity["items"][0]["packageId"] == "figma-context"
    assert activity["items"][0]["status"] == "succeeded"

    detail_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native"
    )
    assert detail_response.status_code == 404


def test_marketplace_package_save_returns_localized_validation_detail(test_app):
    client, _ = test_app
    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "figma-context",
            "displayName": "Figma Context",
            "version": "1.0.0",
            "description": "Figma MCP package",
        },
    )
    created = create_response.json()

    save_response = client.put(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native",
        json={
            "targetClient": "codex",
            "packageId": "figma-context",
            "revision": created["revision"],
            "manifest": {
                "name": "wrong-id",
                "version": "0.2.0",
            },
            "packageFiles": [],
        },
    )

    assert save_response.status_code == 400
    body = save_response.json()["detail"]
    assert body["errorCode"] == "marketplace.validation.invalid_manifest_shape"
    assert body["message"]
    assert [result["code"] for result in body["validationResults"]] == [
        "marketplace.validation.invalid_manifest_shape",
        "marketplace.validation.package_identity_mismatch",
    ]


def test_marketplace_package_export_returns_validation_blocking_detail(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200
    root = _marketplace_registry_root()
    _replace_catalog_packages(
        root,
        [{"targetClient": "codex", "packageId": "broken-plugin"}],
    )
    manifest_path = root / ".agents" / "plugins" / "marketplace.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["plugins"] = [
        {
            "name": "broken-plugin",
            "source": {"source": "local", "path": "./plugins/broken-plugin"},
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    package_root = (
        root / "codex" / "plugins" / "codex-native" / "broken-plugin" / ".codex-plugin"
    )
    package_root.mkdir(parents=True)
    # Corrupt manifest JSON to trigger an error-severity validation result.
    # Missing manifest no longer blocks export because marketplace listings
    # are allowed to declare plugin metadata in lieu of plugin.json.
    (package_root / "plugin.json").write_text("{not valid json", encoding="utf-8")

    detail_response = client.get(
        "/api/v1/marketplace/packages/codex/broken-plugin?packageFormat=codex-native"
    )
    assert detail_response.status_code == 200

    export_response = client.get(
        "/api/v1/marketplace/packages/codex/broken-plugin/export?packageFormat=codex-native",
        params={
            "packageFormat": "codex-native",
            "revision": detail_response.json()["revision"],
        },
    )

    assert export_response.status_code == 400
    body = export_response.json()["detail"]
    assert body["errorCode"] == "marketplace.validation.invalid_manifest_shape"
    assert body["message"]
    assert body["validationResults"][0]["severity"] == "error"


def test_marketplace_openapi_exposes_plugin_and_user_copy_routes(test_app):
    client, _ = test_app

    paths = client.get("/openapi.json").json()["paths"]
    assert "post" in paths["/api/v1/marketplace/plugins/install"]
    assert "post" in paths["/api/v1/marketplace/user-copies/preflight"]
    assert "post" in paths["/api/v1/marketplace/user-copies"]
    assert not any("/marketplace/installations" in path for path in paths)
    assert not any("/marketplace/cleanup-tasks" in path for path in paths)
    assert "503" in paths["/api/v1/marketplace/plugins/install"]["post"]["responses"]
    assert (
        "503" in paths["/api/v1/marketplace/user-copies/preflight"]["post"]["responses"]
    )
    assert "503" in paths["/api/v1/marketplace/user-copies"]["post"]["responses"]


@pytest.mark.parametrize("target_client", ("claude-code", "codex"))
def test_install_api_serializes_terminal_cli_result(
    test_app,
    monkeypatch,
    target_client: str,
) -> None:
    client, _ = test_app

    def install(_service, _user_id, payload):
        assert payload.target_client == target_client
        return {
            "status": "installed",
            "targetClient": target_client,
            "packageId": "review-helper",
            "marketplaceId": "aileron-team-tools",
            "workspaceId": "workspace-1",
            "operationId": "a" * 32,
            "stage": "completed",
            "exitCode": 0,
            "cliMessage": None,
            "stdout": "installed",
            "stderr": None,
            "truncated": False,
        }

    monkeypatch.setattr(
        "app.modules.marketplace.cli_install." "MarketplaceCliInstallService.install",
        install,
    )

    response = client.post(
        "/api/v1/marketplace/plugins/install",
        json={
            "targetClient": target_client,
            "packageFormat": (
                "claude-native" if target_client == "claude-code" else "codex-native"
            ),
            "packageId": "review-helper",
            "version": "1.2.3",
            "workspaceId": "workspace-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["stage"] == "completed"
    assert response.json()["exitCode"] == 0
    assert "installationId" not in response.json()


def test_install_api_returns_structured_error_context(test_app, monkeypatch) -> None:
    client, _ = test_app

    def install(_service, _user_id, _payload):
        raise MarketplaceCliInstallError(
            "marketplace.workspace.access_denied",
            http_status=403,
        )

    monkeypatch.setattr(
        "app.modules.marketplace.cli_install.MarketplaceCliInstallService.install",
        install,
    )

    response = client.post(
        "/api/v1/marketplace/plugins/install",
        json={
            "targetClient": "codex",
            "packageFormat": "codex-native",
            "packageId": "review-helper",
            "version": "1.2.3",
            "workspaceId": "workspace-1",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "errorCode": "marketplace.workspace.access_denied",
        "message": "You do not have access to manage this workspace",
        "stage": "authorize",
        "source": "plugins/codex/codex-native/review-helper/v1.2.3",
        "destination": "workspace-1",
        "category": "authorization",
    }


def _marketplace_client_with_roles(
    test_app: tuple[TestClient, sessionmaker[Session]],
    create_user,
    _monkeypatch,
    *,
    roles: list[str],
    user_id: str,
) -> TestClient:
    client, session_factory = test_app
    platform_roles = {"admin", "member"}
    platform_role = roles[0] if len(roles) == 1 and roles[0] in platform_roles else None
    user = create_user(
        id=user_id,
        username=user_id,
        email=f"{user_id}@example.local",
        platform_role=platform_role or "member",
        role_status="valid",
    )

    authenticate_client_as(client, user)
    if platform_role is None:
        with session_factory() as session:
            stored_user = session.get(db_models.User, user.id)
            assert stored_user is not None
            stored_user.platform_role = None
            stored_user.role_status = "missing"
            session.commit()
    return client


def test_marketplace_rbac_preserves_missing_actor_unauthorized(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["member"],
        user_id="marketplace-missing-user-id",
    )

    def raise_missing_actor():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=authorization_error_detail(
                "PLATFORM_AUTHORIZATION_DENIED",
                "Unauthorized: User not authenticated",
            ),
        )

    client.app.dependency_overrides[get_authorization_actor] = raise_missing_actor
    client.app.dependency_overrides[marketplace_router.get_marketplace_user_id] = (
        lambda: "marketplace-missing-user-id"
    )

    response = client.get("/api/v1/marketplace/packages")

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "errorCode": "PLATFORM_AUTHORIZATION_DENIED",
        "message": "Unauthorized: User not authenticated",
        "details": {},
    }


def test_marketplace_rbac_allows_member_read_and_blocks_admin_operations(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["member"],
        user_id="marketplace-member",
    )

    def install(_service, _user_id, payload):
        return {
            "status": "installed",
            "targetClient": payload.target_client,
            "packageId": payload.package_id,
            "marketplaceId": "aileron-team-tools",
            "workspaceId": payload.workspace_id,
            "operationId": "a" * 32,
            "stage": "completed",
            "exitCode": 0,
            "cliMessage": None,
            "stdout": "installed",
            "stderr": None,
            "truncated": False,
        }

    monkeypatch.setattr(
        "app.modules.marketplace.cli_install.MarketplaceCliInstallService.install",
        install,
    )

    list_response = client.get("/api/v1/marketplace/packages")
    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "figma-context",
            "displayName": "Figma Context",
            "version": "1.0.0",
            "description": "Figma MCP package",
        },
    )
    settings_response = client.get("/api/v1/marketplace/settings")
    init_response = client.post("/api/v1/marketplace/version-control/init")
    repository_response = client.get("/api/v1/marketplace/version-control/repository")
    registry_status_response = client.get("/api/v1/marketplace/version-control/changes")
    registry_commits_response = client.get(
        "/api/v1/marketplace/version-control/commits"
    )
    settings_save_response = client.put(
        "/api/v1/marketplace/settings",
        json={
            "name": "Member Registry",
            "owner": {
                "name": "Member",
                "email": "member@example.local",
            },
            "description": "Member should not save settings",
        },
    )
    activity_response = client.get("/api/v1/marketplace/activities")
    import_scan_response = client.post(
        "/api/v1/marketplace/imports/scan",
        json={
            "targetClient": "codex",
            "sourceKind": "git",
            "source": "https://example.com/org/repo.git",
        },
    )
    install_response = client.post(
        "/api/v1/marketplace/plugins/install",
        json={
            "targetClient": "codex",
            "packageFormat": "codex-native",
            "packageId": "figma-context",
            "version": "1.2.3",
            "workspaceId": "workspace-1",
        },
    )

    assert list_response.status_code == 200
    assert create_response.status_code == 403
    assert settings_response.status_code == 403
    assert init_response.status_code == 403
    assert repository_response.status_code == 403
    assert registry_status_response.status_code == 403
    assert registry_commits_response.status_code == 403
    assert settings_save_response.status_code == 403
    assert activity_response.status_code == 200
    assert import_scan_response.status_code == 403
    assert install_response.status_code == 200
    assert create_response.json()["detail"] == {
        "errorCode": "PLATFORM_AUTHORIZATION_DENIED",
        "message": "You do not have permission to use this Marketplace action",
        "details": {},
    }


def test_marketplace_registry_root_is_shared_across_registry_managers(
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
    init_response = admin_client.post("/api/v1/marketplace/version-control/init")
    admin_settings_response = admin_client.get("/api/v1/marketplace/settings")

    second_admin_client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-shared-second-admin",
    )
    second_admin_settings_response = second_admin_client.get(
        "/api/v1/marketplace/settings"
    )

    assert init_response.status_code == 200
    assert admin_settings_response.status_code == 200
    assert second_admin_settings_response.status_code == 200
    assert admin_settings_response.json()["rootPath"] == str(
        _marketplace_registry_root()
    )
    assert second_admin_settings_response.json()["rootPath"] == str(
        _marketplace_registry_root()
    )
    assert "/users/" not in admin_settings_response.json()["rootPath"]


def test_marketplace_rbac_rejects_local_user_without_platform_role(
    test_app,
    create_user,
):
    client, session_factory = test_app
    user_id = "marketplace-realm-role-user"
    user = create_user(
        id=user_id,
        username=user_id,
        email=f"{user_id}@example.local",
        platform_role="member",
        role_status="valid",
    )

    authenticate_client_as(client, user)
    with session_factory() as session:
        stored_user = session.get(db_models.User, user.id)
        assert stored_user is not None
        stored_user.platform_role = None
        stored_user.role_status = "missing"
        session.commit()

    list_response = client.get("/api/v1/marketplace/packages")
    assert list_response.status_code == 403
    assert list_response.json()["detail"]["errorCode"] == (
        "PLATFORM_AUTHORIZATION_DENIED"
    )


def test_marketplace_rbac_uses_local_member_role_for_permissions(
    test_app,
    create_user,
):
    client, _ = test_app
    initialize_response = client.post("/api/v1/marketplace/version-control/init")
    assert initialize_response.status_code == 200
    user_id = "marketplace-permission-claim-user"
    user = create_user(
        id=user_id,
        username=user_id,
        email=f"{user_id}@example.local",
        platform_role="member",
        role_status="valid",
    )

    authenticate_client_as(client, user)

    root = _marketplace_registry_root()
    _replace_catalog_packages(
        root,
        [
            {
                "targetClient": "codex",
                "packageId": "figma-context",
            }
        ],
    )
    package_path = (
        root / "codex" / "plugins" / "codex-native" / "figma-context" / ".codex-plugin"
    )
    package_path.mkdir(parents=True, exist_ok=True)
    (package_path / "plugin.json").write_text(
        json.dumps({"name": "figma-context", "version": "0.1.0"}),
        encoding="utf-8",
    )

    detail_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native"
    )
    create_denied_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "denied-package",
            "displayName": "Denied Package",
            "version": "1.0.0",
            "description": "Should not create",
        },
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["packageId"] == "figma-context"
    assert create_denied_response.status_code == 403


def test_marketplace_rbac_does_not_grant_admin_actions_to_local_member(
    test_app,
    create_user,
):
    client, _ = test_app
    user_id = "marketplace-authz-permission-user"
    user = create_user(
        id=user_id,
        username=user_id,
        email=f"{user_id}@example.local",
        platform_role="member",
        role_status="valid",
    )

    authenticate_client_as(client, user)

    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "authz-package",
            "displayName": "Authz Package",
            "version": "1.0.0",
            "description": "Local member must not create packages",
        },
    )

    assert create_response.status_code == 403
    assert create_response.json()["detail"]["errorCode"] == (
        "PLATFORM_AUTHORIZATION_DENIED"
    )


def test_marketplace_rbac_rejects_local_user_with_missing_role_status(
    test_app,
    create_user,
):
    client, session_factory = test_app
    user_id = "marketplace-group-user"
    user = create_user(
        id=user_id,
        username=user_id,
        email=f"{user_id}@example.local",
        platform_role="admin",
        role_status="valid",
    )
    authenticate_client_as(client, user)
    with session_factory() as session:
        stored_user = session.get(db_models.User, user.id)
        assert stored_user is not None
        stored_user.role_status = "missing"
        session.commit()

    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "group-package",
            "displayName": "Group Package",
            "version": "1.0.0",
            "description": "Invalid local role status must be rejected",
        },
    )

    assert create_response.status_code == 403
    assert create_response.json()["detail"]["errorCode"] == (
        "PLATFORM_AUTHORIZATION_DENIED"
    )


def test_marketplace_rbac_rejects_missing_platform_role_without_default_fallback(
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
    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "figma-context",
            "displayName": "Figma Context",
            "version": "1.0.0",
            "description": "Figma MCP package",
        },
    )
    import_scan_response = client.post(
        "/api/v1/marketplace/imports/scan",
        json={
            "targetClient": "codex",
            "sourceKind": "git",
            "source": "https://token@example.com/org/repo.git",
        },
    )

    assert list_response.status_code == 403
    assert settings_response.status_code == 403
    assert create_response.status_code == 403
    assert import_scan_response.status_code == 403
    assert create_response.json()["detail"]["errorCode"] == (
        "PLATFORM_AUTHORIZATION_DENIED"
    )
    assert import_scan_response.json()["detail"]["errorCode"] == (
        "PLATFORM_AUTHORIZATION_DENIED"
    )


def test_marketplace_rbac_blocks_member_content_and_registry_management(
    test_app,
    create_user,
    monkeypatch,
):
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["member"],
        user_id="marketplace-member-content",
    )

    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "figma-context",
            "displayName": "Figma Context",
            "version": "1.0.0",
            "description": "Figma MCP package",
        },
    )
    delete_response = client.delete(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native",
        params={"packageFormat": "codex-native"},
    )
    registry_response = client.post("/api/v1/marketplace/version-control/init")
    registry_git_response = client.post("/api/v1/marketplace/version-control/init")

    assert create_response.status_code == 403
    assert delete_response.status_code == 403
    assert registry_response.status_code == 403
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
        roles=["admin"],
        user_id="marketplace-importer",
    )

    token_response = client.post(
        "/api/v1/marketplace/imports/scan",
        json={
            "targetClient": "codex",
            "sourceKind": "git",
            "source": "https://token@example.com/org/repo.git",
        },
    )

    def fake_git(_repo_root, *args, **_kwargs):
        Path(args[-1]).mkdir(parents=True)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.import_sources.git_allow_failure",
        fake_git,
    )

    valid_response = client.post(
        "/api/v1/marketplace/imports/scan",
        json={
            "targetClient": "codex",
            "sourceKind": "git",
            "source": "https://example.com/org/repo.git",
        },
    )

    assert token_response.status_code == 400
    assert (
        token_response.json()["detail"]["errorCode"]
        == "marketplace.import.validation.https_token_unsupported"
    )
    assert valid_response.status_code == 200
    assert valid_response.json() == []


def test_marketplace_import_upload_accepts_local_zip_source(test_app):
    client, _ = test_app
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            ".agents/plugins/marketplace.json",
            json.dumps(
                {
                    "plugins": [
                        {
                            "name": "uploaded-plugin",
                            "source": {
                                "source": "local",
                                "path": "./plugins/uploaded-plugin",
                            },
                        }
                    ],
                }
            ),
        )
        archive.writestr(
            "plugins/uploaded-plugin/.codex-plugin/plugin.json",
            json.dumps(
                {
                    "name": "uploaded-plugin",
                    "version": "0.1.0",
                    "description": "Uploaded package",
                }
            ),
        )

    upload_response = client.post(
        "/api/v1/marketplace/imports/upload",
        data={"targetClient": "codex"},
        files={"file": ("marketplace.zip", buffer.getvalue(), "application/zip")},
    )

    assert upload_response.status_code == 200
    body = upload_response.json()
    assert body["fileName"] == "marketplace.zip"
    assert body["source"]["targetClient"] == "codex"
    assert body["source"]["sourceKind"] == "local"
    scan_response = client.post(
        "/api/v1/marketplace/imports/scan", json=body["source"]
    )
    assert scan_response.status_code == 200
    assert scan_response.json()[0]["packageId"] == "uploaded-plugin"


def test_marketplace_import_endpoint_copies_selected_candidates(test_app):
    client, _ = test_app
    response = client.post("/api/v1/marketplace/version-control/init")
    assert response.status_code == 200
    root = _marketplace_registry_root()
    source_root = root.parent / "import-sources" / "codex-api-import"
    manifest_path = source_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "name": "figma-context",
                        "source": {
                            "source": "local",
                            "path": "./plugins/figma-context",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    package_path = source_root / "plugins" / "figma-context" / ".codex-plugin"
    package_path.mkdir(parents=True)
    (package_path / "plugin.json").write_text(
        json.dumps(
            {
                "name": "figma-context",
                "version": "0.1.0",
                "description": "Figma context package",
            }
        ),
        encoding="utf-8",
    )
    source_payload = {
        "targetClient": "codex",
        "sourceKind": "local",
        "source": str(source_root),
    }

    scan_response = client.post(
        "/api/v1/marketplace/imports/scan", json=source_payload
    )
    candidates = scan_response.json()
    candidates[0]["import"] = {
        "version": "0.1.0",
        "overwrite": False,
    }
    import_response = client.post(
        "/api/v1/marketplace/imports",
        json={
            "source": source_payload,
            "candidates": candidates,
        },
    )

    assert scan_response.status_code == 200
    assert import_response.status_code == 200
    body = import_response.json()
    assert body["imported"][0]["packageId"] == "figma-context"
    assert body["failed"] == []
    assert (
        root
        / "codex"
        / "plugins"
        / "codex-native"
        / "figma-context"
        / ".codex-plugin"
        / "plugin.json"
    ).exists()

    detail_response = client.get(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native"
    )
    detail = detail_response.json()
    assert detail_response.status_code == 200
    assert detail["manifestMetadata"]["importSource"]["source"] == str(source_root)
    assert detail["manifestMetadata"]["importSource"]["packageId"] == "figma-context"
    assert (
        client.post(
            "/api/v1/marketplace/version-control/stage",
            json={"all": True},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/marketplace/version-control/commit",
            json={"message": "Commit imported Figma context"},
        ).status_code
        == 200
    )
    tags = subprocess.run(
        ["git", "tag", "--list"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert tags == []

    internal_manifest_path = (
        root
        / "codex"
        / "plugins"
        / "codex-native"
        / "figma-context"
        / ".codex-plugin"
        / "plugin.json"
    )
    internal_manifest = json.loads(internal_manifest_path.read_text(encoding="utf-8"))
    internal_manifest["version"] = "0.1.0-internal.2"
    internal_manifest_path.write_text(json.dumps(internal_manifest), encoding="utf-8")
    assert (
        client.post(
            "/api/v1/marketplace/version-control/stage",
            json={"paths": [internal_manifest_path.relative_to(root).as_posix()]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/marketplace/version-control/commit",
            json={"message": "Commit updated Figma context"},
        ).status_code
        == 200
    )
    tags = subprocess.run(
        ["git", "tag", "--list"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert tags == []

    remote_path = root.parent / "marketplace-registry.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert (
        client.put(
            "/api/v1/marketplace/version-control/remote",
            json={"remoteUrl": str(remote_path)},
        ).status_code
        == 200
    )
    publish_response = client.post(
        "/api/v1/marketplace/version-control/branches/publish",
        json={"remote": "origin"},
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["affectedTotal"] == 1
    published_refs = subprocess.run(
        ["git", "show-ref"],
        cwd=remote_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert published_refs == [
        f"{publish_response.json()['headSha']} refs/heads/main",
    ]

    internal_manifest["version"] = "0.1.0-internal.3"
    internal_manifest_path.write_text(json.dumps(internal_manifest), encoding="utf-8")
    assert (
        client.post(
            "/api/v1/marketplace/version-control/stage",
            json={"paths": [internal_manifest_path.relative_to(root).as_posix()]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/marketplace/version-control/commit",
            json={"message": "Commit latest Figma context"},
        ).status_code
        == 200
    )
    push_response = client.post("/api/v1/marketplace/version-control/push")
    assert push_response.status_code == 200
    assert push_response.json()["success"] is True
    remote_tags = subprocess.run(
        ["git", "tag", "--list"],
        cwd=remote_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert remote_tags == []

    readme_path = internal_manifest_path.parent.parent / "README.md"
    readme_path.write_text("Changed without a new version\n", encoding="utf-8")
    assert (
        client.post(
            "/api/v1/marketplace/version-control/stage",
            json={"paths": [readme_path.relative_to(root).as_posix()]},
        ).status_code
        == 200
    )
    duplicate_release_response = client.post(
        "/api/v1/marketplace/version-control/commit",
        json={"message": "Attempt to reuse internal version"},
    )
    assert duplicate_release_response.status_code == 200


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

    init_response = client.post("/api/v1/marketplace/version-control/init")
    create_response = client.post(
        "/api/v1/marketplace/packages",
        json={
            "packageFormat": "codex-native",
            "targetClients": ["codex"],
            "packageId": "figma-context",
            "displayName": "Figma Context",
            "version": "1.0.0",
            "description": "Figma MCP package",
        },
    )
    delete_response = client.delete(
        "/api/v1/marketplace/packages/codex/figma-context?packageFormat=codex-native",
        params={"packageFormat": "codex-native"},
    )

    assert init_response.status_code == 200
    assert create_response.status_code == 201
    assert delete_response.status_code == 200


def test_marketplace_registry_force_unlock_clears_stale_on_disk_lock(test_app):
    """force-unlock returns a target-safe shared mutation result."""
    client, _ = test_app
    client.post("/api/v1/marketplace/version-control/init")

    root = _marketplace_registry_root()
    stale_lock = root / ".git" / "index.lock"
    stale_lock.parent.mkdir(parents=True, exist_ok=True)
    stale_lock.write_text("stale", encoding="utf-8")
    stale_time = time.time() - 60
    os.utime(stale_lock, (stale_time, stale_time))
    assert stale_lock.exists()

    response = client.post("/api/v1/marketplace/version-control/force-unlock")

    assert response.status_code == 200
    body = response.json()
    assert body["affectedTotal"] == 1
    assert "cleared" not in body
    assert not stale_lock.exists()
