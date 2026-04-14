"""Claude Code API 測試案例 - Scripts / Skills 文件操作"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from fastapi import status

from app.modules.claude_code.file_collections.scripts_router import get_scripts_service
from app.modules.claude_code.file_collections.skills_router import get_skills_service
from app.modules.file_system import (
    FileManagementException,
    FileTreeResponse,
    FileContentResponse,
)
from app.modules.file_system import FileNode

from .helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubFileCollectionService:
    tree_result: Optional[FileTreeResponse] = None
    tree_error: Optional[Exception] = None
    read_result: Optional[FileContentResponse] = None
    read_error: Optional[Exception] = None
    write_response: Optional[dict[str, Any]] = None
    write_error: Optional[Exception] = None
    create_response: Optional[dict[str, Any]] = None
    create_error: Optional[Exception] = None
    delete_response: Optional[dict[str, Any]] = None
    delete_error: Optional[Exception] = None
    copy_response: Optional[dict[str, Any]] = None
    copy_error: Optional[Exception] = None
    move_response: Optional[dict[str, Any]] = None
    move_error: Optional[Exception] = None
    batch_delete_response: Optional[dict[str, Any]] = None
    batch_delete_error: Optional[Exception] = None
    plugin_skills_result: Optional[list[Any]] = None
    plugin_skills_error: Optional[Exception] = None
    recorded_calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(
        default_factory=list
    )

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.recorded_calls.append((name, args, kwargs))

    def get_tree(self, path: str, scope: Optional[str], includeHidden: bool, maxDepth):
        self._record("get_tree", path, scope, includeHidden, maxDepth)
        if self.tree_error:
            raise self.tree_error
        assert self.tree_result is not None
        return self.tree_result

    def read_file(self, path: str, scope: Optional[str]):
        self._record("read_file", path, scope)
        if self.read_error:
            raise self.read_error
        assert self.read_result is not None
        return self.read_result

    def write_file(
        self,
        path: str,
        content: str,
        scope: Optional[str],
        expectedVersionId: Optional[str],
    ):
        self._record("write_file", path, content, scope, expectedVersionId)
        if self.write_error:
            raise self.write_error
        assert self.write_response is not None
        return self.write_response

    def create_entry(
        self, path: str, entry_type: str, scope: Optional[str], content: str
    ) -> dict[str, Any]:
        self._record("create_entry", path, entry_type, scope, content)
        if self.create_error:
            raise self.create_error
        assert self.create_response is not None
        return self.create_response

    def delete_entry(
        self, path: str, scope: Optional[str], recursive: bool
    ) -> dict[str, Any]:
        self._record("delete_entry", path, scope, recursive)
        if self.delete_error:
            raise self.delete_error
        assert self.delete_response is not None
        return self.delete_response

    def copy_entry(
        self,
        sourcePath: str,
        destPath: str,
        sourceScope: Optional[str],
        destScope: Optional[str],
        overwrite: bool,
    ) -> dict[str, Any]:
        self._record(
            "copy_entry", sourcePath, destPath, sourceScope, destScope, overwrite
        )
        if self.copy_error:
            raise self.copy_error
        assert self.copy_response is not None
        return self.copy_response

    def move_entry(
        self,
        sourcePath: str,
        destPath: str,
        sourceScope: Optional[str],
        destScope: Optional[str],
        overwrite: bool,
    ) -> dict[str, Any]:
        self._record(
            "move_entry", sourcePath, destPath, sourceScope, destScope, overwrite
        )
        if self.move_error:
            raise self.move_error
        assert self.move_response is not None
        return self.move_response

    def batch_delete(
        self, paths: List[str], scope: Optional[str], recursive: bool
    ) -> dict[str, Any]:
        self._record("batch_delete", paths, scope, recursive)
        if self.batch_delete_error:
            raise self.batch_delete_error
        assert self.batch_delete_response is not None
        return self.batch_delete_response

    def get_plugin_skills(self) -> list[Any]:
        self._record("get_plugin_skills")
        if self.plugin_skills_error:
            raise self.plugin_skills_error
        assert self.plugin_skills_result is not None
        return self.plugin_skills_result


def _tree_node(name: str, *, node_type: str = "file", scope: str = "project") -> FileNode:
    return FileNode(
        id=f"{scope}:{name}",
        name=name,
        path=f"/{name}",
        type=node_type,
        scope=scope,
        size=0,
        updatedAt="2024-01-01T00:00:00Z",
        depth=0,
        children=[],
        hasChildren=False,
    )


def test_fc_001_scripts_tree_root(client):
    tree = FileTreeResponse(
        path="/",
        scope="project",
        nodes=[_tree_node("hello.py")],
        total=1,
    )
    service = StubFileCollectionService(tree_result=tree)

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"path": "/", "scope": "project"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] == 1



def test_fc_002_lazy_children(client):
    child = _tree_node("nested.py")
    tree = FileTreeResponse(path="/src", scope="project", nodes=[child], total=1)
    service = StubFileCollectionService(tree_result=tree)

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree/children",
            params={"path": "/src", "scope": "project"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["nodes"][0]["name"] == "nested.py"


def test_fc_003_invalid_scope(client):
    service = StubFileCollectionService(
        tree_error=FileManagementException(
            "INVALID_SCOPE", "invalid", status_code=400, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"scope": "invalid"},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_fc_004_read_content(client):
    content = FileContentResponse(
        path="/hello.py",
        scope="project",
        content="print('hi')",
        size=11,
        updatedAt="2024-01-01T00:00:00Z",
        versionId="v1",
        contentHash="hash",
    )
    service = StubFileCollectionService(read_result=content)

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/content",
            params={"path": "/hello.py", "scope": "project"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["content"] == "print('hi')"


def test_fc_005_read_missing(client):
    service = StubFileCollectionService(
        read_error=FileManagementException(
            "FILE_NOT_FOUND", "missing", status_code=404, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/content",
            params={"path": "/missing.py", "scope": "project"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_fc_006_write_with_version(client):
    service = StubFileCollectionService(
        write_response={"updatedAt": "2024-01-01T00:00:01Z", "versionId": "v2"}
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/content",
            params={
                "path": "/hello.py",
                "content": "print('updated')",
                "scope": "project",
                "expectedVersionId": "v1",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["versionId"] == "v2"


def test_fc_007_write_version_conflict(client):
    service = StubFileCollectionService(
        write_error=FileManagementException(
            "VERSION_CONFLICT", "conflict", status_code=409, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/content",
            params={
                "path": "/hello.py",
                "content": "print('oops')",
                "scope": "project",
                "expectedVersionId": "old",
            },
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["code"] == "VERSION_CONFLICT"


def test_fc_008_create_file_and_directory(client):
    service = StubFileCollectionService(
        create_response={"type": "file", "createdAt": "2024-01-01T00:00:00Z"}
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts",
            params={"path": "new-script.js", "type": "file", "scope": "user"},
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["data"]["type"] == "file"


def test_fc_009_delete_entries(client):
    service = StubFileCollectionService(delete_response={"type": "file"})

    with override_dependency(get_scripts_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts",
            params={"path": "old.js", "scope": "project"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["type"] == "file"


def test_fc_010_copy_between_scopes(client):
    service = StubFileCollectionService(copy_response={"type": "file"})

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/copy",
            params={
                "sourcePath": "a.py",
                "destPath": "b.py",
                "sourceScope": "project",
                "destScope": "user",
                "overwrite": True,
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["destScope"] == "user"


def test_fc_011_move_between_scopes(client):
    service = StubFileCollectionService(move_response={"type": "file"})

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/move",
            params={
                "sourcePath": "a.py",
                "destPath": "b.py",
                "sourceScope": "user",
                "destScope": "project",
                "overwrite": True,
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["destScope"] == "project"


def test_fc_012_move_conflict(client):
    service = StubFileCollectionService(
        move_error=FileManagementException(
            "FILE_ALREADY_EXISTS", "exists", status_code=409, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/move",
            params={
                "sourcePath": "a.py",
                "destPath": "b.py",
                "sourceScope": "user",
                "destScope": "project",
            },
        )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_fc_013_batch_delete_success(client):
    service = StubFileCollectionService(
        batch_delete_response={
            "success": 3,
            "failed": 0,
            "succeeded": 3,
            "total": 3,
            "results": [
                {"path": "file1.js", "success": True},
                {"path": "dir1", "success": True},
                {"path": "file2.py", "success": True}
            ]
        }
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/batch-delete",
            params={
                "paths": ["file1.js", "dir1", "file2.py"],
                "scope": "project",
                "recursive": True,
            },
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["succeeded"] == 3
    assert data["failed"] == 0
    assert data["total"] == 3


def test_fc_014_batch_delete_partial_failure(client):
    service = StubFileCollectionService(
        batch_delete_response={
            "succeeded": 2,
            "failed": 1,
            "total": 3,
            "results": [
                {"path": "file1.js", "success": True},
                {"path": "missing.js", "success": False, "error": "File not found"},
                {"path": "file2.py", "success": True}
            ]
        }
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/batch-delete",
            params={
                "paths": ["file1.js", "missing.js", "file2.py"],
                "scope": "project",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["succeeded"] == 2
    assert data["failed"] == 1


def test_fc_015_batch_delete_invalid_scope(client):
    service = StubFileCollectionService(
        batch_delete_error=FileManagementException(
            "INVALID_SCOPE", "invalid", status_code=400, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/batch-delete",
            params={
                "paths": ["file1.js"],
                "scope": "invalid",
            },
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_fc_019_max_depth_valid_value(client):
    tree = FileTreeResponse(
        path="/",
        scope="project",
        nodes=[_tree_node("nested.js")],
        total=1,
    )
    service = StubFileCollectionService(tree_result=tree)

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"path": "/", "scope": "project", "maxDepth": 5},
        )

    assert response.status_code == status.HTTP_200_OK
    assert service.recorded_calls[0][0] == "get_tree"
    assert service.recorded_calls[0][1][3] == 5  # maxDepth parameter


def test_fc_020_max_depth_boundary_value(client):
    tree = FileTreeResponse(
        path="/",
        scope="project",
        nodes=[_tree_node("file.js")],
        total=1,
    )
    service = StubFileCollectionService(tree_result=tree)

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"path": "/", "scope": "project", "maxDepth": 1},
        )

    assert response.status_code == status.HTTP_200_OK
    assert service.recorded_calls[0][1][3] == 1


def test_fc_021_max_depth_zero_invalid(client):
    with override_dependency(get_scripts_service, lambda: StubFileCollectionService()):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"maxDepth": 0},
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "maxDepth" in response.json()["detail"][0]["loc"]


def test_fc_022_max_depth_negative_invalid(client):
    with override_dependency(get_scripts_service, lambda: StubFileCollectionService()):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"maxDepth": -1},
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "maxDepth" in response.json()["detail"][0]["loc"]


def test_fc_023_include_hidden_files(client):
    hidden_node = _tree_node(".hidden.js")
    visible_node = _tree_node("visible.js")
    tree = FileTreeResponse(
        path="/",
        scope="project",
        nodes=[hidden_node, visible_node],
        total=2,
    )
    service = StubFileCollectionService(tree_result=tree)

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"path": "/", "scope": "project", "includeHidden": True},
        )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["nodes"]) == 2
    assert service.recorded_calls[0][1][2] is True  # includeHidden


def test_fc_024_exclude_hidden_files_default(client):
    visible_node = _tree_node("visible.js")
    tree = FileTreeResponse(
        path="/",
        scope="project",
        nodes=[visible_node],
        total=1,
    )
    service = StubFileCollectionService(tree_result=tree)

    with override_dependency(get_scripts_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/tree",
            params={"path": "/", "scope": "project"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["nodes"]) == 1
    assert service.recorded_calls[0][1][2] is False  # includeHidden default


def test_fc_025_expected_version_id_mismatch(client):
    service = StubFileCollectionService(
        write_error=FileManagementException(
            "VERSION_CONFLICT", "Version mismatch", status_code=409, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/content",
            params={
                "path": "/test.js",
                "content": "updated content",
                "scope": "project",
                "expectedVersionId": "v1",  # Old version
            },
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["code"] == "VERSION_CONFLICT"


def test_fc_026_missing_expected_version_id(client):
    service = StubFileCollectionService(
        write_response={"updatedAt": "2024-01-01T00:00:01Z", "versionId": "v2"}
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/content",
            params={
                "path": "/test.js",
                "content": "updated content",
                "scope": "project",
                # No expectedVersionId provided
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert service.recorded_calls[0][1][3] is None  # expectedVersionId


def test_fc_027_recursive_delete_non_empty_directory(client):
    service = StubFileCollectionService(delete_response={"type": "directory"})

    with override_dependency(get_scripts_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts",
            params={
                "path": "non-empty-dir",
                "scope": "project",
                "recursive": True,
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert service.recorded_calls[0][1][2] is True  # recursive


def test_fc_028_non_recursive_delete_non_empty_directory_fails(client):
    service = StubFileCollectionService(
        delete_error=FileManagementException(
            "DIRECTORY_NOT_EMPTY", "Directory not empty", status_code=409, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts",
            params={
                "path": "non-empty-dir",
                "scope": "project",
                "recursive": False,
            },
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["code"] == "DIRECTORY_NOT_EMPTY"


def test_fc_029_overwrite_existing_file(client):
    service = StubFileCollectionService(copy_response={"type": "file"})

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/copy",
            params={
                "sourcePath": "source.js",
                "destPath": "existing.js",
                "sourceScope": "project",
                "destScope": "project",
                "overwrite": True,
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert service.recorded_calls[0][1][4] is True  # overwrite


def test_fc_030_refuse_overwrite_existing_file(client):
    service = StubFileCollectionService(
        copy_error=FileManagementException(
            "FILE_ALREADY_EXISTS", "File already exists", status_code=409, details={}
        )
    )

    with override_dependency(get_scripts_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/scripts/copy",
            params={
                "sourcePath": "source.js",
                "destPath": "existing.js",
                "sourceScope": "project",
                "destScope": "project",
                "overwrite": False,
            },
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["code"] == "FILE_ALREADY_EXISTS"
