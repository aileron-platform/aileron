from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.revision import compute_revision
from app.modules.cli_settings.slash_commands.config import SlashCommandTool
from app.modules.cli_settings.slash_commands.router import create_slash_commands_router
from app.modules.cli_settings.slash_commands.catalog import (
    CliSlashCommandDuplicateError,
    CliSlashCommandNotFoundError,
)


EMPTY_REVISION = compute_revision("{}")


class FakeCliSlashCommandService:
    def __init__(self) -> None:
        self.fail_with = None
        self.last_get_request = None
        self.last_delete_request = None

    def _maybe_fail(self):
        if self.fail_with:
            raise self.fail_with

    def list_scopes(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "items": [],
            "availableScopes": [{"scope": scope or "user", "readOnly": False}],
        }

    def get_scope(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "documents": [
                {
                    "path": "team/hello.md",
                    "scope": scope,
                    "size": "1KB",
                    "format": "markdown",
                }
            ],
        }

    def get_document(self, workspace_id, scope, path):
        self._maybe_fail()
        self.last_get_request = {
            "workspace_id": workspace_id,
            "scope": scope,
            "path": path,
        }
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "document": {
                "path": path,
                "scope": scope,
                "size": "1KB",
                "format": "markdown",
                "content": "# hello",
            },
        }

    def create_document(self, workspace_id, scope, payload):
        self._maybe_fail()
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "document": {
                "path": payload.path,
                "scope": scope,
                "size": "1KB",
                "format": "markdown",
                "content": payload.content,
            },
        }

    def update_document(self, workspace_id, scope, payload):
        self._maybe_fail()
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "document": {
                "path": payload.path,
                "scope": scope,
                "size": "1KB",
                "format": "markdown",
                "content": payload.content,
            },
        }

    def delete_document(self, workspace_id, scope, path, *, revision=None):
        self._maybe_fail()
        self.last_delete_request = {
            "workspace_id": workspace_id,
            "scope": scope,
            "path": path,
        }
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "path": path,
            "revision": EMPTY_REVISION,
            "deleted": True,
        }


def _client(service: FakeCliSlashCommandService, monkeypatch) -> TestClient:
    monkeypatch.setattr(
        "app.modules.cli_settings.slash_commands.router.make_slash_command_service_dependency",
        lambda tool: (lambda workspace_id: service),
    )
    app = FastAPI()
    app.include_router(
        create_slash_commands_router(SlashCommandTool.CODEX),
        prefix="/workspaces/{workspace_id}/cli-settings",
    )
    return TestClient(app)


def test_cli_slash_commands_router_happy_paths(monkeypatch) -> None:
    service = FakeCliSlashCommandService()
    client = _client(service, monkeypatch)

    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/slash-commands",
            params={"scope": "user"},
        ).status_code
        == 200
    )
    assert (
        client.get("/workspaces/ws-1/cli-settings/codex/slash-commands/user").json()[
            "scope"
        ]
        == "user"
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/slash-commands/user/content",
            params={"path": "team/hello.md"},
        ).json()["document"]["path"]
        == "team/hello.md"
    )
    assert service.last_get_request == {
        "workspace_id": "ws-1",
        "scope": "user",
        "path": "team/hello.md",
    }

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user",
        json={
            "path": "ops/new.md",
            "content": "# new",
            "revision": EMPTY_REVISION,
        },
    )
    assert response.status_code == 201
    assert response.json()["document"]["path"] == "ops/new.md"

    response = client.put(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user/content",
        json={
            "path": "core/hello.md",
            "content": "# updated",
            "revision": EMPTY_REVISION,
        },
    )
    assert response.status_code == 200
    assert response.json()["document"]["path"] == "core/hello.md"

    response = client.delete(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user/content",
        params={"path": "team/hello.md", "revision": EMPTY_REVISION},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert service.last_delete_request == {
        "workspace_id": "ws-1",
        "scope": "user",
        "path": "team/hello.md",
    }


def test_cli_slash_commands_router_openapi_excludes_extension_query(
    monkeypatch,
) -> None:
    service = FakeCliSlashCommandService()
    client = _client(service, monkeypatch)

    schema = client.get("/openapi.json").json()
    operation = schema["paths"][
        "/workspaces/{workspace_id}/cli-settings/codex/slash-commands/{scope}/content"
    ]["get"]
    parameter_names = {parameter["name"] for parameter in operation["parameters"]}

    assert parameter_names == {"workspace_id", "scope", "path"}


def test_cli_slash_commands_router_maps_not_found(monkeypatch) -> None:
    service = FakeCliSlashCommandService()
    client = _client(service, monkeypatch)

    service.fail_with = CliSlashCommandNotFoundError("missing")
    response = client.get(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user/content",
        params={"path": "missing.md"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["errorCode"] == "404_NOT_FOUND"


def test_cli_slash_commands_router_maps_duplicate(monkeypatch) -> None:
    service = FakeCliSlashCommandService()
    service.fail_with = CliSlashCommandDuplicateError("already exists")
    client = _client(service, monkeypatch)

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user",
        json={"path": "new.md", "content": "# new", "revision": EMPTY_REVISION},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "errorCode": "DUPLICATE_FILE_NAME",
        "message": "already exists",
    }


def test_cli_slash_commands_router_requires_revision_for_mutations(monkeypatch) -> None:
    service = FakeCliSlashCommandService()
    client = _client(service, monkeypatch)

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user",
        json={"path": "new.md", "content": "# new"},
    )

    assert response.status_code == 422
