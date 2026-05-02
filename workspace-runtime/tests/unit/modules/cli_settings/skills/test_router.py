from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.cli_settings.skills.config import SkillTool
from app.modules.cli_settings.skills.router import create_skills_router
from app.modules.file_system import FileManagementException


class FakeSkillService:
    def __init__(self):
        self.fail_with = None

    def _maybe_fail(self):
        if self.fail_with:
            raise self.fail_with

    def get_tree(self, path, scope, include_hidden, max_depth):
        self._maybe_fail()
        return {"path": path, "scope": scope, "nodes": [], "total": 0}

    def read_file(self, path, scope):
        self._maybe_fail()
        return {"path": path, "scope": scope, "content": "hello", "size": 5, "updatedAt": "2026-03-28T00:00:00Z"}

    def write_file(self, path, content, scope, expected_version_id):
        self._maybe_fail()
        return {"updatedAt": "2026-03-28T00:00:00Z", "versionId": "v1"}

    def create_entry(self, path, type, scope, content):
        self._maybe_fail()
        return {"path": path, "scope": scope, "type": type}

    def delete_entry(self, path, scope, recursive):
        self._maybe_fail()
        return {"type": "file"}

    def copy_entry(self, source_path, dest_path, source_scope, dest_scope, overwrite):
        self._maybe_fail()
        return {"type": "file"}

    def move_entry(self, source_path, dest_path, source_scope, dest_scope, overwrite):
        self._maybe_fail()
        return {"type": "file"}

    def batch_delete(self, paths, scope, recursive):
        self._maybe_fail()
        return {"total": len(paths), "succeeded": len(paths), "failed": 0, "results": []}

def _client(service: FakeSkillService, monkeypatch, tool: SkillTool = SkillTool.GEMINI) -> TestClient:
    monkeypatch.setattr(
        "app.modules.cli_settings.skills.router.make_skill_service_dependency",
        lambda t: (lambda workspace_id: service),
    )
    app = FastAPI()
    app.include_router(create_skills_router(tool), prefix="/workspaces/{workspace_id}/cli-settings")
    return TestClient(app)


def test_skills_router_happy_paths(monkeypatch) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)

    assert client.get("/workspaces/ws-1/cli-settings/gemini/skills/tree").status_code == 200
    assert client.get("/workspaces/ws-1/cli-settings/gemini/skills/tree/children", params={"path": "/a"}).status_code == 200
    assert client.get("/workspaces/ws-1/cli-settings/gemini/skills/content", params={"path": "/a.md"}).status_code == 200
    assert client.put("/workspaces/ws-1/cli-settings/gemini/skills/content", params={"path": "/a.md", "content": "hi"}).status_code == 200
    assert client.post("/workspaces/ws-1/cli-settings/gemini/skills", params={"path": "/a.md", "type": "file"}).status_code == 201
    assert client.delete("/workspaces/ws-1/cli-settings/gemini/skills", params={"path": "/a.md"}).status_code == 200
    assert client.post("/workspaces/ws-1/cli-settings/gemini/skills/copy", params={"sourcePath": "/a", "destPath": "/b"}).status_code == 200
    assert client.post("/workspaces/ws-1/cli-settings/gemini/skills/move", params={"sourcePath": "/a", "destPath": "/b"}).status_code == 200
    assert client.post("/workspaces/ws-1/cli-settings/gemini/skills/batch-delete", params=[("paths", "/a"), ("paths", "/b")]).status_code == 200


def test_skills_router_error_mapping(monkeypatch) -> None:
    service = FakeSkillService()
    service.fail_with = FileManagementException("broken", status_code=409)
    client = _client(service, monkeypatch)

    response = client.get("/workspaces/ws-1/cli-settings/gemini/skills/tree")
    assert response.status_code == 409

    service.fail_with = RuntimeError("boom")
    response = client.get("/workspaces/ws-1/cli-settings/gemini/skills/content", params={"path": "/a.md"})
    assert response.status_code == 500


def test_skills_router_plugin_endpoint_absent(monkeypatch) -> None:
    client = _client(FakeSkillService(), monkeypatch, tool=SkillTool.GEMINI)
    response = client.get("/workspaces/ws-1/cli-settings/gemini/skills/plugins")
    assert response.status_code == 404
