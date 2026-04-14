from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.file_system import FileManagementException

scripts_router_module = importlib.import_module("app.modules.claude_code.file_collections.scripts_router")


class FakeScriptsService:
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
        return {"path": path, "scope": scope, "content": "echo hi", "size": 7, "updatedAt": "2026-03-28T00:00:00Z"}

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


def _client(service: FakeScriptsService) -> TestClient:
    app = FastAPI()
    app.include_router(scripts_router_module.router, prefix="/workspaces/ws-1/claude")
    app.dependency_overrides[scripts_router_module.get_scripts_service] = lambda: service
    return TestClient(app)


def test_scripts_router_happy_paths() -> None:
    client = _client(FakeScriptsService())

    assert client.get("/workspaces/ws-1/claude/scripts/tree").status_code == 200
    assert client.get("/workspaces/ws-1/claude/scripts/tree/children", params={"path": "/bin"}).status_code == 200
    assert client.get("/workspaces/ws-1/claude/scripts/content", params={"path": "/run.sh"}).status_code == 200
    assert client.put("/workspaces/ws-1/claude/scripts/content", params={"path": "/run.sh", "content": "echo hi"}).status_code == 200
    assert client.post("/workspaces/ws-1/claude/scripts", params={"path": "/run.sh", "type": "file"}).status_code == 201
    assert client.delete("/workspaces/ws-1/claude/scripts", params={"path": "/run.sh"}).status_code == 200
    assert client.post("/workspaces/ws-1/claude/scripts/copy", params={"sourcePath": "/run.sh", "destPath": "/copy.sh"}).status_code == 200
    assert client.post("/workspaces/ws-1/claude/scripts/move", params={"sourcePath": "/run.sh", "destPath": "/moved.sh"}).status_code == 200
    assert client.post("/workspaces/ws-1/claude/scripts/batch-delete", params=[("paths", "/a"), ("paths", "/b")]).status_code == 200


def test_scripts_router_error_mapping() -> None:
    service = FakeScriptsService()
    service.fail_with = FileManagementException("broken", status_code=404)
    client = _client(service)

    response = client.get("/workspaces/ws-1/claude/scripts/tree")
    assert response.status_code == 404

    service.fail_with = RuntimeError("boom")
    response = client.get("/workspaces/ws-1/claude/scripts/content", params={"path": "/run.sh"})
    assert response.status_code == 500
