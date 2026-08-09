from app.modules.file_system.local_history import WorkspaceLocalHistory
from app.modules.file_system.operations import FileService


def test_upload_replace_snapshots_existing_target(tmp_path):
    history = WorkspaceLocalHistory(
        history_root=tmp_path / "history",
        workspace_id="ws-1",
    )
    service = FileService(
        root_path=tmp_path / "workspace",
        workspace_id="ws-1",
        local_history=history,
    )
    service.write_file("docs/readme.md", "old upload")

    service.upload_file_bytes(
        target_path="docs",
        filename="readme.md",
        content=b"new upload",
        default_strategy="replace",
        resolutions=[],
    )

    entry = history.list_entries(path="docs/readme.md")[0]
    assert entry["operation"] == "upload"
