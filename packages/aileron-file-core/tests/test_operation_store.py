from datetime import datetime, timedelta, timezone

from aileron_file_core import BackgroundFileOperationStore


def test_operation_store_owns_creation_updates_and_scope_isolation() -> None:
    now = datetime(2026, 7, 30, tzinfo=timezone.utc)
    store: BackgroundFileOperationStore[str] = BackgroundFileOperationStore(
        operation_prefix="extract",
        now=lambda: now,
    )

    operation = store.create(
        scope_key="kb-1",
        message="Preparing",
        metadata={"access_role": "editor"},
    )
    updated = store.update(
        scope_key="kb-1",
        operation_id=operation.operation_id,
        status="completed",
        progress=4.0,
        message="Done",
        result="result",
    )

    assert updated is operation
    assert operation.operation_id.startswith("extract-")
    assert operation.progress == 1.0
    assert operation.completed_at == now
    assert operation.metadata == {"access_role": "editor"}
    assert store.get(scope_key="kb-1", operation_id=operation.operation_id) is operation
    assert store.get(scope_key="kb-2", operation_id=operation.operation_id) is None


def test_operation_store_removes_expired_artifact(tmp_path) -> None:
    current = [datetime(2026, 7, 30, tzinfo=timezone.utc)]
    store: BackgroundFileOperationStore[bytes] = BackgroundFileOperationStore(
        operation_prefix="archive",
        now=lambda: current[0],
    )
    artifact = tmp_path / "archive.zip"
    artifact.write_bytes(b"zip")
    operation = store.create(scope_key="workspace", message="Preparing")
    store.update(
        scope_key="workspace",
        operation_id=operation.operation_id,
        status="completed",
        artifact_path=artifact,
        expires_at=current[0] + timedelta(seconds=1),
    )

    current[0] += timedelta(seconds=2)

    assert store.get(scope_key="workspace", operation_id=operation.operation_id) is None
    assert artifact.exists() is False
