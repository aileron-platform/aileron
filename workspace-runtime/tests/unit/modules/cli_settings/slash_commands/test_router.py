from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.cli_settings.slash_commands.config import SlashCommandTool
from app.modules.cli_settings.slash_commands.router import create_slash_commands_router
from app.modules.cli_settings.slash_commands.service import (
    CliSlashCommandAmbiguousError,
    CliSlashCommandDuplicateError,
    CliSlashCommandNotFoundError,
)


class FakeCliSlashCommandService:
    def __init__(self) -> None:
        self.fail_with = None

    def _maybe_fail(self):
        if self.fail_with:
            raise self.fail_with

    def list_scopes(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scopes": [{"scope": scope or "user", "documents": []}],
        }

    def get_scope(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "documents": [{"fileName": "hello.md", "scope": scope, "size": "1KB", "format": "markdown"}],
        }

    def get_document(self, workspace_id, scope, file_name):
        self._maybe_fail()
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "document": {
                "fileName": file_name,
                "scope": scope,
                "size": "1KB",
                "format": "markdown",
                "content": "# hello",
                "namespace": "team",
            },
        }

    def create_document(self, workspace_id, scope, payload):
        self._maybe_fail()
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "document": {
                "fileName": payload.file_name,
                "scope": scope,
                "size": "1KB",
                "format": "markdown",
                "content": payload.content,
                "namespace": payload.namespace,
            },
        }

    def update_document(self, workspace_id, scope, file_name, payload):
        self._maybe_fail()
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "document": {
                "fileName": file_name,
                "scope": scope,
                "size": "1KB",
                "format": "markdown",
                "content": payload.content,
                "namespace": payload.namespace,
            },
        }

    def delete_document(self, workspace_id, scope, file_name):
        self._maybe_fail()
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "fileName": file_name,
            "deleted": True,
        }


def _client(service: FakeCliSlashCommandService, monkeypatch) -> TestClient:
    monkeypatch.setattr(
        "app.modules.cli_settings.slash_commands.router.make_slash_command_service_dependency",
        lambda tool: (lambda workspace_id: service),
    )
    app = FastAPI()
    app.include_router(create_slash_commands_router(SlashCommandTool.CODEX), prefix="/workspaces/{workspace_id}/cli-settings")
    return TestClient(app)


def test_cli_slash_commands_router_happy_paths(monkeypatch) -> None:
    client = _client(FakeCliSlashCommandService(), monkeypatch)

    assert client.get("/workspaces/ws-1/cli-settings/codex/slash-commands", params={"scope": "user"}).status_code == 200
    assert client.get("/workspaces/ws-1/cli-settings/codex/slash-commands/user").json()["scope"] == "user"
    assert client.get("/workspaces/ws-1/cli-settings/codex/slash-commands/user/hello.md").json()["document"]["namespace"] == "team"

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user",
        json={"fileName": "new.md", "content": "# new", "namespace": "ops"},
    )
    assert response.status_code == 201
    assert response.json()["document"]["fileName"] == "new.md"

    response = client.put(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user/hello.md",
        json={"content": "# updated", "namespace": "core"},
    )
    assert response.status_code == 200
    assert response.json()["document"]["namespace"] == "core"

    response = client.delete("/workspaces/ws-1/cli-settings/codex/slash-commands/user/hello.md")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_cli_slash_commands_router_maps_not_found_and_ambiguous(monkeypatch) -> None:
    service = FakeCliSlashCommandService()
    client = _client(service, monkeypatch)

    service.fail_with = CliSlashCommandNotFoundError("missing")
    response = client.get("/workspaces/ws-1/cli-settings/codex/slash-commands/user/missing.md")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "404_NOT_FOUND"

    service.fail_with = CliSlashCommandAmbiguousError("duplicate docs")
    response = client.put(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user/hello.md",
        json={"content": "# updated"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "AMBIGUOUS_DOCUMENT"


def test_cli_slash_commands_router_maps_duplicate(monkeypatch) -> None:
    service = FakeCliSlashCommandService()
    service.fail_with = CliSlashCommandDuplicateError("already exists")
    client = _client(service, monkeypatch)

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/slash-commands/user",
        json={"fileName": "new.md", "content": "# new"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "error": "DUPLICATE_FILE_NAME",
        "message": "already exists",
    }
