from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.modules.marketplace.models import (
    MarketplacePackageDeleteResult,
    MarketplacePackageMutationResult,
)
from tests.helpers.manager_session import authenticate_client_as


def _marketplace_client_with_roles(
    test_app,
    create_user,
    _monkeypatch,
    *,
    roles: list[str],
    user_id: str,
) -> TestClient:
    client, _ = test_app
    platform_roles = {"admin", "member"}
    platform_role = roles[0] if len(roles) == 1 and roles[0] in platform_roles else None
    user = create_user(
        id=user_id,
        username=user_id,
        email=f"{user_id}@example.local",
        platform_role=platform_role,
        role_status="valid" if platform_role else "missing",
    )

    authenticate_client_as(client, user)
    return client


def _create_codex_package_with_mcp(
    client: TestClient,
    *,
    package_id: str,
    server_name: str = "db",
) -> str:
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "provider": "codex",
            "packageId": package_id,
            "displayName": "Demo",
            "description": "Demo package",
        },
    )
    assert created.status_code == 201
    revision = created.json()["revision"]
    mcp = client.post(
        f"/api/v1/marketplace/packages/codex/{package_id}/mcp-servers",
        json={
            "revision": revision,
            "name": server_name,
            "server": {"command": "x"},
        },
    )
    assert mcp.status_code == 200
    return mcp.json()["revision"]


def test_draft_discard_does_not_require_revision(
    test_app, create_user, monkeypatch
) -> None:
    calls: list[tuple[str, str, str]] = []
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-resource-user",
    )

    def discard_draft(self, user_id: str, provider: str, package_id: str):
        calls.append((user_id, provider, package_id))
        return MarketplacePackageDeleteResult(deleted=True, revision="rev2")

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.discard_draft_package",
        discard_draft,
        raising=False,
    )

    response = client.delete("/api/v1/marketplace/packages/codex/demo/draft")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert calls == [("marketplace-resource-user", "codex", "demo")]


def test_package_refresh_not_found_does_not_leave_ghost_detail(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-refresh-missing-user",
    )

    response = client.post("/api/v1/marketplace/packages/codex/does-not-exist/refresh")

    assert response.status_code == 404
    detail_response = client.get("/api/v1/marketplace/packages/codex/does-not-exist")
    assert detail_response.status_code == 404


def test_root_document_route_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-root-user",
    )

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.load_root_document",
        lambda self, user_id, provider, package_id: {
            "path": "AGENTS.md",
            "content": "# Rules",
        },
        raising=False,
    )

    response = client.get("/api/v1/marketplace/packages/codex/demo/root-document")

    assert response.status_code == 200
    assert response.json()["path"] == "AGENTS.md"


def test_command_content_route_uses_query_path(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-command-user",
    )

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.load_document",
        lambda self, user_id, provider, package_id, resource_type, path: {
            "id": path,
            "title": "review",
            "path": path,
            "resourceType": resource_type,
            "content": "# Review",
        },
        raising=False,
    )

    response = client.get(
        "/api/v1/marketplace/packages/codex/demo/commands/content?path=commands%2Fteam%2Freview.md"
    )

    assert response.status_code == 200
    assert response.json()["path"] == "commands/team/review.md"


def test_create_document_returns_canonical_mutation_payload(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-create-resource-user",
    )

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.create_document",
        lambda self, user_id, provider, package_id, resource_type, payload: (
            MarketplacePackageMutationResult(
                path="commands/hello.md",
                revision="rev2",
            )
        ),
        raising=False,
    )

    response = client.post(
        "/api/v1/marketplace/packages/codex/demo/commands",
        json={
            "revision": "rev1",
            "path": "commands/hello.md",
            "content": "# hi",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "success": True,
        "path": "commands/hello.md",
        "revision": "rev2",
        "ownerFilePath": None,
        "baseEntryFingerprint": None,
    }


def test_move_document_endpoint(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-move-user",
    )

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.move_document",
        lambda self, user_id, provider, package_id, resource_type, payload: (
            MarketplacePackageMutationResult(
                path="commands/new.md",
                revision="rev2",
            )
        ),
        raising=False,
    )

    response = client.post(
        "/api/v1/marketplace/packages/codex/demo/commands/move",
        json={
            "revision": "rev1",
            "previousPath": "commands/old.md",
            "nextPath": "commands/new.md",
        },
    )

    assert response.status_code == 200
    assert response.json()["path"] == "commands/new.md"
    assert response.json()["revision"] == "rev2"


def test_rename_endpoint_gone(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-rename-gone-user",
    )

    response = client.post(
        "/api/v1/marketplace/packages/codex/demo/commands/rename",
        json={},
    )

    assert response.status_code == 404


def test_command_create_rejects_unrooted_path(
    test_app, create_user, monkeypatch
) -> None:
    from app.modules.marketplace.workflows.registry_operations import (
        MarketplacePathError,
    )

    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-create-path-user",
    )

    def _raise_path_error(self, user_id, provider, package_id, resource_type, payload):
        raise MarketplacePathError("marketplace.package.path_escape")

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.create_document",
        _raise_path_error,
        raising=False,
    )

    response = client.post(
        "/api/v1/marketplace/packages/codex/demo/commands",
        json={
            "revision": "rev1",
            "path": "ASDF/ASDF",
            "content": "# ASDF\n",
        },
    )

    assert response.status_code == 400


def test_mcp_get_put_delete_by_path_name(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-mcp-path-user",
    )
    calls: list[tuple[str, str | None]] = []

    def mutation_result(revision: str) -> MarketplacePackageMutationResult:
        return MarketplacePackageMutationResult(
            path=".mcp.json",
            revision=revision,
            owner_file_path=".mcp.json",
            base_entry_fingerprint="fp",
        )

    def create_server(self, user_id, provider, package_id, payload):
        calls.append(("create", payload.name))
        return mutation_result("rev2")

    def get_server(self, user_id, provider, package_id, name, owner_file_path):
        calls.append(("get", name))
        assert owner_file_path == ".mcp.json"
        return {
            "name": name,
            "path": ".mcp.json",
            "server": {"command": "x"},
            "baseEntryFingerprint": "fp",
            "ownerFilePath": ".mcp.json",
        }

    def save_server(self, user_id, provider, package_id, name, payload):
        calls.append(("put", name))
        return mutation_result("rev3")

    def delete_server(self, user_id, provider, package_id, name, payload):
        calls.append(("delete", name))
        assert payload.owner_file_path == ".mcp.json"
        assert payload.base_entry_fingerprint == "fp-next"
        return MarketplacePackageMutationResult(
            path=".mcp.json",
            revision="rev4",
            owner_file_path=".mcp.json",
            base_entry_fingerprint=None,
        )

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.create_mcp_server",
        create_server,
        raising=False,
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.get_mcp_server",
        get_server,
        raising=False,
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.save_mcp_server",
        save_server,
        raising=False,
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.delete_mcp_server",
        delete_server,
        raising=False,
    )

    create = client.post(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers",
        json={"revision": "rev1", "name": "db", "server": {"command": "x"}},
    )
    assert create.status_code == 200
    got = client.get(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/db",
        params={"ownerFilePath": ".mcp.json"},
    )
    assert got.status_code == 200
    put = client.put(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/db",
        json={
            "revision": "rev2",
            "server": {"command": "y"},
            "ownerFilePath": ".mcp.json",
            "baseEntryFingerprint": "fp",
        },
    )
    assert put.status_code == 200
    delete = client.request(
        "DELETE",
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/db",
        json={
            "revision": "rev3",
            "ownerFilePath": ".mcp.json",
            "baseEntryFingerprint": "fp-next",
        },
    )
    assert delete.status_code == 200
    assert calls == [
        ("create", "db"),
        ("get", "db"),
        ("put", "db"),
        ("delete", "db"),
    ]


def test_mcp_server_route_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-mcp-user",
    )

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.get_mcp_server",
        lambda self, user_id, provider, package_id, name, owner_file_path: {
            "name": name,
            "path": owner_file_path,
            "server": {"command": "node"},
            "baseEntryFingerprint": "fp",
            "ownerFilePath": ".mcp.json",
        },
        raising=False,
    )

    response = client.get(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/local",
        params={"ownerFilePath": ".mcp.json"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "local"


def test_mcp_http_contract_requires_owner_tokens_and_forbids_create_tokens(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-mcp-token-contract-user",
    )

    missing_get_owner = client.get(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/local"
    )
    create_with_owner = client.post(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers",
        json={
            "revision": "rev1",
            "name": "local",
            "server": {"command": "node"},
            "ownerFilePath": ".mcp.json",
            "baseEntryFingerprint": "entry-fp",
        },
    )
    update_without_owner = client.put(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/local",
        json={
            "revision": "rev1",
            "server": {"command": "node"},
        },
    )
    update_with_body_name = client.put(
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/local",
        json={
            "revision": "rev1",
            "name": "different",
            "server": {"command": "node"},
            "ownerFilePath": ".mcp.json",
            "baseEntryFingerprint": "entry-fp",
        },
    )
    delete_without_owner = client.request(
        "DELETE",
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/local",
        json={"revision": "rev1"},
    )
    delete_with_body_name = client.request(
        "DELETE",
        "/api/v1/marketplace/packages/codex/demo/mcp-servers/local",
        json={
            "revision": "rev1",
            "name": "different",
            "ownerFilePath": ".mcp.json",
            "baseEntryFingerprint": "entry-fp",
        },
    )

    assert missing_get_owner.status_code == 422
    assert create_with_owner.status_code == 422
    assert update_without_owner.status_code == 422
    assert update_with_body_name.status_code == 422
    assert delete_without_owner.status_code == 422
    assert delete_with_body_name.status_code == 422


def test_mcp_list_emits_token_for_source_capture(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-mcp-list-token-user",
    )
    _create_codex_package_with_mcp(client, package_id="mcp-list-token")

    listed = client.get("/api/v1/marketplace/packages/codex/mcp-list-token/mcp-servers")
    wrong_owner = client.get(
        "/api/v1/marketplace/packages/codex/mcp-list-token/mcp-servers/db",
        params={"ownerFilePath": "config/other.json"},
    )

    assert listed.status_code == 200
    body = listed.json()
    assert any("baseEntryFingerprint" in item for item in body)
    assert any("ownerFilePath" in item for item in body)
    assert wrong_owner.status_code == 404


def test_mcp_save_stale_entry_fingerprint_conflicts(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-mcp-stale-token-user",
    )
    revision = _create_codex_package_with_mcp(
        client,
        package_id="mcp-stale-token",
    )

    response = client.put(
        "/api/v1/marketplace/packages/codex/mcp-stale-token/mcp-servers/db",
        json={
            "revision": revision,
            "server": {"command": "y"},
            "ownerFilePath": ".mcp.json",
            "baseEntryFingerprint": "stale-fp",
        },
    )

    assert response.status_code == 409


def test_basic_endpoint_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-basic-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.get_basic_metadata",
        lambda self, user_id, provider, package_id: {
            "revision": "rev1",
            "displayName": "Demo",
            "description": "",
            "catalogMetadata": {},
            "manifestMetadata": {},
            "lifecycleStatus": "draft",
            "validationResults": [],
        },
        raising=False,
    )
    response = client.get("/api/v1/marketplace/packages/codex/demo/basic")
    assert response.status_code == 200


def test_hooks_endpoint_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-hooks-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.get_hooks",
        lambda self, user_id, provider, package_id: {
            "revision": "rev1",
            "sources": [],
            "hookCapabilities": {"mode": "sources", "groups": []},
        },
        raising=False,
    )
    response = client.get("/api/v1/marketplace/packages/codex/demo/hooks")
    assert response.status_code == 200


def test_root_document_revision_conflict_maps_409(
    test_app, create_user, monkeypatch
) -> None:
    from app.modules.marketplace.workflows.registry_operations import (
        MarketplaceConflictError,
    )

    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-root-conflict-user",
    )

    def raise_conflict(self, user_id, provider, package_id, revision, content):
        raise MarketplaceConflictError("marketplace.package.revision_conflict")

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.save_root_document",
        raise_conflict,
        raising=False,
    )

    response = client.put(
        "/api/v1/marketplace/packages/codex/demo/root-document",
        json={"revision": "stale-revision", "content": "x"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]


def test_skill_write_invalid_path_maps_400(test_app, create_user, monkeypatch) -> None:
    from app.modules.marketplace.workflows.registry_operations import (
        MarketplacePathError,
    )

    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skill-path-user",
    )

    def raise_path_error(self, user_id, provider, package_id, revision, path, content):
        raise MarketplacePathError("marketplace.package.path_escape")

    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.write_skill_file",
        raise_path_error,
        raising=False,
    )

    response = client.put(
        "/api/v1/marketplace/packages/codex/demo/skills/content?path=../escape.md",
        json={"revision": "rev1", "content": "x"},
    )

    assert response.status_code == 400


def test_skills_tree_endpoint_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skills-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.list_skill_files",
        lambda self, user_id, provider, package_id: {
            "path": "skills",
            "scope": None,
            "nodes": [],
            "total": 0,
        },
        raising=False,
    )
    response = client.get("/api/v1/marketplace/packages/codex/demo/skills/tree")
    assert response.status_code == 200


def test_skills_tree_endpoint_returns_entry_type(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skills-type-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.list_skill_files",
        lambda self, user_id, provider, package_id: {
            "path": "skills",
            "scope": None,
            "nodes": [
                {
                    "id": "skills",
                    "path": "skills",
                    "name": "skills",
                    "type": "directory",
                },
                {
                    "id": "skills/example/SKILL.md",
                    "path": "skills/example/SKILL.md",
                    "name": "SKILL.md",
                    "type": "file",
                },
            ],
            "total": 2,
        },
        raising=False,
    )

    response = client.get("/api/v1/marketplace/packages/codex/demo/skills/tree")

    assert response.status_code == 200
    assert response.json()["nodes"] == [
        {"id": "skills", "path": "skills", "name": "skills", "type": "directory"},
        {
            "id": "skills/example/SKILL.md",
            "path": "skills/example/SKILL.md",
            "name": "SKILL.md",
            "type": "file",
        },
    ]
    assert response.json()["total"] == 2


def test_skills_tree_returns_unified_nodes_shape(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skills-unified-user",
    )
    package_path = (
        Path(get_settings().MARKETPLACE_STORAGE_PATH)
        / "registry"
        / "codex"
        / "plugins"
        / "demo"
        / "skills"
        / "demo"
    )
    package_path.mkdir(parents=True, exist_ok=True)
    (package_path / "SKILL.md").write_text("# Demo", encoding="utf-8")

    response = client.get("/api/v1/marketplace/packages/codex/demo/skills/tree")

    assert response.status_code == 200
    body = response.json()
    assert "nodes" in body and "total" in body
    if body["nodes"]:
        node = body["nodes"][0]
        assert {"id", "name", "path", "type"} <= set(node)


def test_skill_content_returns_filecontentresponse_shape(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skill-content-unified-user",
    )
    package_path = (
        Path(get_settings().MARKETPLACE_STORAGE_PATH)
        / "registry"
        / "codex"
        / "plugins"
        / "demo"
        / "skills"
        / "demo"
    )
    package_path.mkdir(parents=True, exist_ok=True)
    (package_path / "SKILL.md").write_text("# Demo", encoding="utf-8")

    response = client.get(
        "/api/v1/marketplace/packages/codex/demo/skills/content?path=skills/demo/SKILL.md"
    )

    assert response.status_code == 200
    body = response.json()
    assert {"path", "content", "size", "revision"} <= set(body)
    assert "versionId" not in body and "contentHash" not in body


def test_missing_skill_content_maps_to_not_found(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skill-content-missing-user",
    )

    response = client.get(
        "/api/v1/marketplace/packages/codex/demo/skills/content"
        "?path=skills%2Fdemo%2Fmissing.yaml"
    )

    assert response.status_code == 404
    assert response.json()["detail"]


def test_invalid_skill_content_path_maps_to_bad_request(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skill-content-invalid-path-user",
    )

    response = client.get(
        "/api/v1/marketplace/packages/codex/demo/skills/content?path=..%2Fescape.yaml"
    )

    assert response.status_code == 400
    assert response.json()["detail"]


def test_files_tree_endpoint_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-files-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.list_package_files_tree",
        lambda self, user_id, provider, package_id: {
            "path": "",
            "scope": None,
            "nodes": [],
            "total": 0,
        },
        raising=False,
    )
    response = client.get("/api/v1/marketplace/packages/codex/demo/files/tree")
    assert response.status_code == 200


def test_files_tree_endpoint_returns_entry_type(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-files-type-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.list_package_files_tree",
        lambda self, user_id, provider, package_id: {
            "path": "",
            "scope": None,
            "nodes": [
                {"id": "docs", "path": "docs", "name": "docs", "type": "directory"},
                {
                    "id": "docs/readme.md",
                    "path": "docs/readme.md",
                    "name": "readme.md",
                    "type": "file",
                },
            ],
            "total": 2,
        },
        raising=False,
    )

    response = client.get("/api/v1/marketplace/packages/codex/demo/files/tree")

    assert response.status_code == 200
    assert response.json()["nodes"] == [
        {"id": "docs", "path": "docs", "name": "docs", "type": "directory"},
        {
            "id": "docs/readme.md",
            "path": "docs/readme.md",
            "name": "readme.md",
            "type": "file",
        },
    ]
    assert response.json()["total"] == 2


def test_file_content_endpoint_reads_managed_resource_files(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-file-read-managed-user",
    )
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "provider": "claude-code",
            "packageId": "managed-read-demo",
            "displayName": "Demo",
            "description": "Demo package",
        },
    )
    assert created.status_code == 201, created.text
    created_style = client.post(
        "/api/v1/marketplace/packages/claude-code/managed-read-demo/output-styles",
        json={
            "revision": created.json()["revision"],
            "path": "output-styles/ASF.md",
            "content": "# ASF\n",
        },
    )
    assert created_style.status_code == 200, created_style.text

    response = client.get(
        "/api/v1/marketplace/packages/claude-code/managed-read-demo/files/content"
        "?path=output-styles%2FASF.md"
    )

    assert response.status_code == 200, response.text
    assert response.json()["path"] == "output-styles/ASF.md"
    assert response.json()["content"] == "# ASF\n"


def test_skill_move_endpoint_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skill-move-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.move_skill_entry",
        lambda self, user_id, provider, package_id, revision, previous_path, next_path: (
            MarketplacePackageMutationResult(
                path=next_path,
                revision="rev2",
            )
        ),
        raising=False,
    )

    response = client.post(
        "/api/v1/marketplace/packages/codex/demo/skills/move",
        json={
            "revision": "rev1",
            "previousPath": "skills/example/SKILL.md",
            "nextPath": "skills/example/RENAMED.md",
        },
    )

    assert response.status_code == 200


def test_file_move_endpoint_exists(test_app, create_user, monkeypatch) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-file-move-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_mutations.MarketplacePackageMutationWorkflow.move_package_file_entry",
        lambda self, user_id, provider, package_id, revision, previous_path, next_path: (
            MarketplacePackageMutationResult(
                path=next_path,
                revision="rev2",
            )
        ),
        raising=False,
    )

    response = client.post(
        "/api/v1/marketplace/packages/codex/demo/files/move",
        json={
            "revision": "rev1",
            "previousPath": "docs/readme.md",
            "nextPath": "docs/archive.md",
        },
    )

    assert response.status_code == 200


def test_file_upload_endpoint_writes_package_file(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-file-upload-user",
    )
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "provider": "codex",
            "packageId": "upload-demo",
            "displayName": "Demo",
            "description": "Demo package",
        },
    )
    assert created.status_code == 201, created.text

    uploaded = client.post(
        "/api/v1/marketplace/packages/codex/upload-demo/files/upload",
        data={
            "revision": created.json()["revision"],
            "targetPath": "docs",
            "defaultStrategy": "keep-both",
            "resolutions": "[]",
        },
        files=[("files", ("readme.bin", b"\x00\xffdemo", "application/octet-stream"))],
    )

    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["succeeded"] == 1
    assert uploaded.json()["items"][0]["status"] == "created"
    tree = client.get("/api/v1/marketplace/packages/codex/upload-demo/files/tree")
    assert tree.status_code == 200, tree.text
    assert any(node["path"] == "docs/readme.bin" for node in tree.json()["nodes"])


def test_file_upload_endpoint_rejects_managed_roots(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-file-upload-managed-user",
    )
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "provider": "codex",
            "packageId": "upload-managed-demo",
            "displayName": "Demo",
            "description": "Demo package",
        },
    )
    assert created.status_code == 201, created.text

    uploaded = client.post(
        "/api/v1/marketplace/packages/codex/upload-managed-demo/files/upload",
        data={
            "revision": created.json()["revision"],
            "targetPath": ".",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files=[("files", (".mcp.json", b"{}", "application/json"))],
    )

    assert uploaded.status_code == 400


def test_skill_upload_endpoint_enforces_skills_scope(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-skill-upload-user",
    )
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "provider": "codex",
            "packageId": "upload-skill-demo",
            "displayName": "Demo",
            "description": "Demo package",
        },
    )
    assert created.status_code == 201, created.text

    rejected = client.post(
        "/api/v1/marketplace/packages/codex/upload-skill-demo/skills/upload",
        data={
            "revision": created.json()["revision"],
            "targetPath": "docs",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files={"files": ("SKILL.md", b"# Skill", "text/markdown")},
    )
    assert rejected.status_code == 400

    accepted = client.post(
        "/api/v1/marketplace/packages/codex/upload-skill-demo/skills/upload",
        data={
            "revision": created.json()["revision"],
            "targetPath": "skills/demo",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files={"files": ("SKILL.md", b"# Skill", "text/markdown")},
    )
    assert accepted.status_code == 200, accepted.text

    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w") as archive:
        archive.writestr("archived/SKILL.md", "# Archived")
    current = client.get("/api/v1/marketplace/packages/codex/upload-skill-demo")
    stored = client.post(
        "/api/v1/marketplace/packages/codex/upload-skill-demo/skills/upload",
        data={
            "revision": current.json()["revision"],
            "targetPath": "skills",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files={
            "files": (
                "skills.zip",
                archive_buffer.getvalue(),
                "application/zip",
            )
        },
    )
    assert stored.status_code == 200, stored.text

    current = client.get("/api/v1/marketplace/packages/codex/upload-skill-demo")
    extracted = client.post(
        "/api/v1/marketplace/packages/codex/upload-skill-demo/skills/extract",
        json={
            "revision": current.json()["revision"],
            "archivePath": "skills/skills.zip",
            "targetPath": "skills",
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )
    assert extracted.status_code == 200, extracted.text
    tree = client.get(
        "/api/v1/marketplace/packages/codex/upload-skill-demo/skills/tree"
    )
    assert "skills/archived/SKILL.md" in str(tree.json())


def test_existing_export_endpoint_is_not_captured_by_document_resource_route(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-export-user",
    )
    monkeypatch.setattr(
        "app.modules.marketplace.workflows.package_reads.MarketplacePackageReadModel.export_package",
        lambda self, user_id, provider, package_id, revision: b"zip",
        raising=False,
    )
    response = client.get(
        "/api/v1/marketplace/packages/codex/demo/export?revision=rev1"
    )
    assert response.status_code == 200


def test_whole_package_save_route_rejects_legacy_payload_shape(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-save-user",
    )

    response = client.put(
        "/api/v1/marketplace/packages/codex/demo",
        json={
            "revision": "rev1",
            "displayName": "Demo",
            "description": "Package",
            "catalogMetadata": {},
            "manifestMetadata": {},
            "readmeMarkdown": "# Demo",
            "featureContent": {
                "hooks": [],
                "mcpServers": [],
                "agents": [],
                "commands": [],
                "outputStyles": [],
                "skills": [],
            },
            "packageFiles": [],
        },
    )

    assert response.status_code == 422


def _create_claude_package_with_mcp(
    client: TestClient,
    *,
    package_id: str,
    server_name: str = "ASDF",
) -> str:
    created = client.post(
        "/api/v1/marketplace/packages",
        json={
            "provider": "claude-code",
            "packageId": package_id,
            "displayName": "Demo",
            "description": "Demo package",
        },
    )
    assert created.status_code == 201, created.text
    revision = created.json()["revision"]
    mcp = client.post(
        f"/api/v1/marketplace/packages/claude-code/{package_id}/mcp-servers",
        json={
            "revision": revision,
            "name": server_name,
            "server": {"command": "x"},
        },
    )
    assert mcp.status_code == 200, mcp.text
    return mcp.json()["revision"]


def test_mcp_save_roundtrip_persists_changes(
    test_app, create_user, monkeypatch
) -> None:
    """Reproduce: PUT save returns 200 but the change is not reflected on read-back."""
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-mcp-roundtrip-user",
    )
    revision = _create_claude_package_with_mcp(client, package_id="mcp-roundtrip")

    listed = client.get(
        "/api/v1/marketplace/packages/claude-code/mcp-roundtrip/mcp-servers"
    )
    assert listed.status_code == 200, listed.text
    item = next(entry for entry in listed.json() if entry["name"] == "ASDF")

    save = client.put(
        "/api/v1/marketplace/packages/claude-code/mcp-roundtrip/mcp-servers/ASDF",
        json={
            "revision": revision,
            "server": {
                "name": "ASDF",
                "description": "ASDFa",
                "transport": "stdio",
                "command": "ASDF",
                "args": ["fASDF"],
                "env": {"ASDF": "ASDF"},
            },
            "ownerFilePath": item["ownerFilePath"],
            "baseEntryFingerprint": item["baseEntryFingerprint"],
        },
    )
    assert save.status_code == 200, save.text

    reread = client.get(
        "/api/v1/marketplace/packages/claude-code/mcp-roundtrip/mcp-servers/ASDF",
        params={"ownerFilePath": item["ownerFilePath"]},
    )
    assert reread.status_code == 200, reread.text
    updated = reread.json()
    assert (
        updated["server"]["command"] == "ASDF"
    ), f"save did not persist; read-back still shows {updated['server']!r}"


def test_whole_package_save_route_requires_package_files(
    test_app, create_user, monkeypatch
) -> None:
    client = _marketplace_client_with_roles(
        test_app,
        create_user,
        monkeypatch,
        roles=["admin"],
        user_id="marketplace-save-required-files-user",
    )
    revision = _create_codex_package_with_mcp(client, package_id="demo")

    response = client.put(
        "/api/v1/marketplace/packages/codex/demo",
        json={
            "provider": "codex",
            "packageId": "demo",
            "revision": revision,
            "listing": {
                "name": "demo",
                "source": {"source": "local", "path": "./plugins/demo"},
            },
            "manifest": {"name": "demo", "version": "0.1.0"},
            "readmeMarkdown": "# Demo",
        },
    )

    assert response.status_code == 422
