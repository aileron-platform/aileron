"""Core file tree related API tests"""

from __future__ import annotations

from pathlib import Path

from app.modules.file_system.router import get_new_file_service
from app.modules.file_system.service import FileService

from .helpers import override_dependency


def _prepare_workspace(base: Path) -> Path:
    workspace = base / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "components").mkdir()
    (workspace / "src" / "components" / "Button.tsx").write_text("export const Button = () => null;\n", encoding="utf-8")
    (workspace / "src" / "index.ts").write_text("export * from './components/Button';\n", encoding="utf-8")
    (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET=1\n", encoding="utf-8")
    return workspace


def test_fl_001_get_file_tree_root(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get("/api/v1/files/tree", params={"path": "/", "maxDepth": 3})

    assert response.status_code == 200
    payload = response.json()
    names = {node["name"] for node in payload["nodes"]}
    assert "src" in names
    assert "README.md" in names
    assert ".env" not in names


def test_fl_002_get_file_tree_include_hidden(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get(
            "/api/v1/files/tree",
            params={"path": "/", "maxDepth": 2, "includeHidden": "true"},
        )

    assert response.status_code == 200
    names = {node["name"] for node in response.json()["nodes"]}
    assert ".env" in names


def test_fl_003_get_directory_children(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get(
            "/api/v1/files/tree/children",
            params={"path": "/src", "maxDepth": 1},
        )

    assert response.status_code == 200
    nodes = response.json()["nodes"]
    names = {node["name"] for node in nodes}
    assert "components" in names
    components = next(node for node in nodes if node["name"] == "components")
    child_names = {child["name"] for child in components.get("children", [])}
    assert "Button.tsx" in child_names
