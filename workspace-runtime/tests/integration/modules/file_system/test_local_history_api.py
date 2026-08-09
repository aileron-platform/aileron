from pathlib import Path

from app.modules.file_system.local_history import WorkspaceLocalHistory
from app.modules.file_system.router import get_new_file_service
from app.modules.file_system.operations import FileService

from .dependency_overrides import override_dependency


def _service_with_history(tmp_path: Path) -> FileService:
    workspace = tmp_path / "workspace"
    history_root = tmp_path / "history"
    workspace.mkdir()
    return FileService(
        root_path=workspace,
        workspace_id="ws-1",
        local_history=WorkspaceLocalHistory(
            history_root=history_root,
            workspace_id="ws-1",
        ),
    )


def test_files_history_lists_and_restores_snapshot(client, tmp_path: Path) -> None:
    service = _service_with_history(tmp_path)

    with override_dependency(get_new_file_service, lambda: service):
        client.put(
            "/api/v1/files/content",
            json={"path": "README.md", "content": "old"},
        )
        first = client.get(
            "/api/v1/files/content",
            params={"path": "README.md"},
        ).json()
        client.put(
            "/api/v1/files/content",
            json={
                "path": "README.md",
                "content": "new",
                "revision": first["revision"],
            },
        )

        history = client.get("/api/v1/files/history", params={"path": "README.md"})
        assert history.status_code == 200
        entries = history.json()["items"]
        assert entries[0]["operation"] == "write"

        current = client.get(
            "/api/v1/files/content",
            params={"path": "README.md"},
        ).json()
        restored = client.post(
            f"/api/v1/files/history/{entries[0]['id']}/restore",
            json={"revision": current["revision"]},
        )

        assert restored.status_code == 200
        assert (
            client.get(
                "/api/v1/files/content",
                params={"path": "README.md"},
            ).json()["content"]
            == "old"
        )


def test_local_history_uses_revision_fields(client, tmp_path: Path) -> None:
    service = _service_with_history(tmp_path)

    with override_dependency(get_new_file_service, lambda: service):
        client.put(
            "/api/v1/files/content",
            json={"path": "a.txt", "content": "hi"},
        )
        client.put(
            "/api/v1/files/content",
            json={"path": "a.txt", "content": "bye", "revision": None},
        )
        history = client.get("/api/v1/files/history", params={"path": "a.txt"}).json()

        entries = history["items"]
        assert entries
        assert {"revisionBefore", "revisionAfter"} <= set(entries[0])
        assert "versionIdBefore" not in entries[0]


def test_files_history_restore_deleted_file_is_create_restore(
    client, tmp_path: Path
) -> None:
    service = _service_with_history(tmp_path)

    with override_dependency(get_new_file_service, lambda: service):
        client.put(
            "/api/v1/files/content",
            json={"path": "deleted.md", "content": "before delete"},
        )
        client.delete("/api/v1/files", params={"path": "deleted.md"})
        entry = client.get(
            "/api/v1/files/history",
            params={"path": "deleted.md"},
        ).json()["items"][0]

        restored = client.post(
            f"/api/v1/files/history/{entry['id']}/restore",
            json={},
        )

        assert restored.status_code == 200
        assert (
            client.get(
                "/api/v1/files/content",
                params={"path": "deleted.md"},
            ).json()["content"]
            == "before delete"
        )
