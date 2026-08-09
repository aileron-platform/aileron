from pathlib import Path

from app.modules.file_system.local_history import WorkspaceLocalHistory
from app.modules.file_system.operations import FileService


def test_write_file_snapshots_existing_content_before_overwrite(tmp_path: Path) -> None:
    history = WorkspaceLocalHistory(
        history_root=tmp_path / "history",
        workspace_id="ws-1",
    )
    service = FileService(
        root_path=tmp_path / "workspace",
        workspace_id="ws-1",
        local_history=history,
    )
    service.write_file("README.md", "old")

    service.write_file("README.md", "new")

    entries = history.list_entries(path="README.md")
    assert len(entries) == 1
    assert entries[0]["operation"] == "write"
    assert Path(entries[0]["snapshotPath"]).read_text(encoding="utf-8") == "old"


def test_delete_move_and_paste_replace_create_snapshots(tmp_path: Path) -> None:
    history = WorkspaceLocalHistory(
        history_root=tmp_path / "history",
        workspace_id="ws-1",
    )
    service = FileService(
        root_path=tmp_path / "workspace",
        workspace_id="ws-1",
        local_history=history,
    )
    service.write_file("delete.md", "delete me")
    service.write_file("move.md", "move me")
    service.write_file("copy-source.md", "copy source")
    service.write_file("target/copy-source.md", "copy dest")

    service.delete_entry("delete.md")
    service.move_entry("move.md", "moved.md")
    service.paste_entries(
        source_paths=["copy-source.md"],
        target_path="target",
        default_strategy="replace",
        resolutions=[],
    )

    operations = [entry["operation"] for entry in history.list_entries()]
    assert "delete" in operations
    assert "move" in operations
    assert "copy" in operations
    assert (
        Path(history.list_entries(path="delete.md")[0]["snapshotPath"]).read_text(
            encoding="utf-8"
        )
        == "delete me"
    )


def test_restore_history_entry_preserves_binary_snapshot(tmp_path: Path) -> None:
    history = WorkspaceLocalHistory(
        history_root=tmp_path / "history",
        workspace_id="ws-1",
    )
    service = FileService(
        root_path=tmp_path / "workspace",
        workspace_id="ws-1",
        local_history=history,
    )
    payload_before = b"\xff\x00before"
    payload_after = b"\x00after"
    service.upload_file_bytes(
        target_path="",
        filename="payload.bin",
        content=payload_before,
        default_strategy="cancel",
        resolutions=[],
    )
    service.upload_file_bytes(
        target_path="",
        filename="payload.bin",
        content=payload_after,
        default_strategy="replace",
        resolutions=[],
    )
    entry_id = history.list_entries(path="payload.bin")[0]["id"]
    current_revision = service.read_file("payload.bin")["revision"]

    result = service.restore_history_entry(
        entry_id,
        revision=current_revision,
    )

    assert result["path"] == "payload.bin"
    assert (service._root_path / "payload.bin").read_bytes() == payload_before
