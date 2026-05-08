"""Skills Router tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.file_system import (
    BatchOperationResponse,
    FileContentResponse,
    FileManagementException,
    FileTreeResponse,
)
from app.modules.claude_code.file_collections.skills_router import (
    get_skills_service,
    router,
)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.workspace_id = "test-workspace"
    return service


@pytest.fixture
def override_service(app, mock_service):
    app.dependency_overrides[get_skills_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.clear()


class TestSkillsRouter:
    def test_get_skills_tree_success(self, client, override_service):
        override_service.get_tree.return_value = FileTreeResponse(path="/", nodes=[], total=0)

        response = client.get("/skills/tree", params={"path": "/"})

        assert response.status_code == 200
        assert response.json()["path"] == "/"

    def test_get_skills_tree_file_management_exception(self, client, override_service):
        override_service.get_tree.side_effect = FileManagementException(
            "Not found",
            status_code=404,
        )

        response = client.get("/skills/tree", params={"path": "/"})

        assert response.status_code == 404

    def test_read_skill_success(self, client, override_service):
        override_service.read_file.return_value = FileContentResponse(
            path="/test.md",
            content="# Test",
            size=6,
            updatedAt=datetime.now().isoformat(),
        )

        response = client.get("/skills/content", params={"path": "/test.md"})

        assert response.status_code == 200
        assert response.json()["content"] == "# Test"

    def test_write_skill_success(self, client, override_service):
        override_service.write_file.return_value = {
            "updatedAt": datetime.now().isoformat(),
            "versionId": "v1",
        }

        response = client.put(
            "/skills/content",
            params={"path": "/test.md", "content": "New content"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["data"]["versionId"] == "v1"

    def test_create_skill_success(self, client, override_service):
        override_service.create_entry.return_value = {"createdAt": datetime.now().isoformat()}

        response = client.post("/skills", params={"path": "/new.md", "type": "file"})

        assert response.status_code == 201
        assert response.json()["success"] is True
        assert response.json()["data"]["type"] == "file"

    def test_delete_skill_success(self, client, override_service):
        override_service.delete_entry.return_value = {"type": "file"}

        response = client.request("DELETE", "/skills", params={"path": "/test.md"})

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["data"]["type"] == "file"

    def test_copy_skill_success(self, client, override_service):
        override_service.copy_entry.return_value = {"type": "file"}

        response = client.post(
            "/skills/copy",
            params={"sourcePath": "/src.md", "destPath": "/dst.md"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["data"]["destPath"] == "/dst.md"

    def test_move_skill_success(self, client, override_service):
        override_service.move_entry.return_value = {"type": "file"}

        response = client.post(
            "/skills/move",
            params={"sourcePath": "/src.md", "destPath": "/dst.md"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["data"]["destPath"] == "/dst.md"

    def test_batch_delete_skills_success(self, client, override_service):
        override_service.batch_delete.return_value = BatchOperationResponse(
            total=2,
            succeeded=2,
            failed=0,
            results=[
                {"path": "/skill1.md", "success": True},
                {"path": "/skill2.md", "success": True},
            ],
        )

        response = client.post(
            "/skills/batch-delete",
            params=[("paths", "/skill1.md"), ("paths", "/skill2.md")],
        )

        assert response.status_code == 200
        assert response.json()["succeeded"] == 2

    def test_get_plugin_skills_exception_returns_empty(self, client, override_service):
        override_service.get_plugin_skills.side_effect = Exception("Plugin error")

        response = client.get("/skills/plugins")

        assert response.status_code == 200
        assert response.json() == {"workspaceId": "test-workspace", "plugins": []}

    def test_get_skills_children_success(self, client, override_service):
        override_service.get_tree.return_value = FileTreeResponse(path="/team", nodes=[], total=0)

        response = client.get("/skills/tree/children", params={"path": "/team", "includeHidden": True, "maxDepth": 2})

        assert response.status_code == 200
        assert response.json()["path"] == "/team"
        override_service.get_tree.assert_called_with("/team", None, True, 2)

    def test_router_maps_generic_exception_to_500(self, client, override_service):
        override_service.get_tree.side_effect = RuntimeError("boom")

        response = client.get("/skills/tree", params={"path": "/"})

        assert response.status_code == 500
        assert response.json()["detail"] == "boom"

    def test_create_skill_maps_file_management_exception(self, client, override_service):
        override_service.create_entry.side_effect = FileManagementException("conflict", status_code=409)

        response = client.post("/skills", params={"path": "/new.md", "type": "file"})

        assert response.status_code == 409
        assert response.json()["detail"]["message"] == "conflict"

    def test_copy_skill_maps_generic_exception(self, client, override_service):
        override_service.copy_entry.side_effect = RuntimeError("copy failed")

        response = client.post(
            "/skills/copy",
            params={"sourcePath": "/src.md", "destPath": "/dst.md"},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "copy failed"
