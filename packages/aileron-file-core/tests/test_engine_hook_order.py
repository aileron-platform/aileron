from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

import pytest

from aileron_file_core import FileCoreError
from aileron_file_core.adapters import RootedFileAdapter, StaticRootResolver
from aileron_file_core.engine import FileOperationEngine
from aileron_file_core.hooks import FileMutationHooks
from aileron_file_core.models import (
    CopyEntryRequest,
    DeleteEntryRequest,
    FileLocator,
    SyncTreeItem,
    SyncTreeRequest,
    WriteTextRequest,
)
from aileron_file_core.policies import FilePolicy
from aileron_file_core.write_lock import ResourceWriteLockKey, ResourceWriteLockManager


class RecordingHooks(FileMutationHooks):
    def __init__(self, *, fail_validation: bool = False) -> None:
        self.events: list[str] = []
        self.fail_validation = fail_validation

    @contextmanager
    def write_barrier(self, locator: FileLocator, operation: str) -> Iterator[None]:
        _ = locator
        self.events.append(f"barrier-enter:{operation}")
        try:
            yield
        finally:
            self.events.append(f"barrier-exit:{operation}")

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = locator
        self.events.append(f"quota:{delta_bytes}")

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        _ = (locator, absolute_path)
        self.events.append(f"snapshot:{relative_path}:{operation}")

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = locator
        self.events.append(f"size:{delta_bytes}")

    def validate_after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        _ = locator
        self.events.append(f"validate:{operation}:{','.join(paths)}")
        if self.fail_validation:
            raise FileCoreError("VALIDATION_FAILED", "Validation failed")

    def after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        _ = locator
        self.events.append(f"invalidate:{operation}:{','.join(paths)}")


class LockInspectingHooks(RecordingHooks):
    def __init__(
        self,
        lock_manager: ResourceWriteLockManager,
        expected_keys: Sequence[ResourceWriteLockKey],
    ) -> None:
        super().__init__()
        self.lock_manager = lock_manager
        self.expected_keys = tuple(expected_keys)

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        super().check_quota(locator, delta_bytes)
        for key in self.expected_keys:
            assert self.lock_manager.is_locked(key)


def _engine(root: Path, hooks: RecordingHooks) -> FileOperationEngine:
    return FileOperationEngine(
        adapter=RootedFileAdapter(root_resolver=StaticRootResolver(root)),
        policy=FilePolicy(max_read_bytes=1024, max_write_bytes=1024),
        hooks=hooks,
    )


def test_write_hook_order_wraps_quota_snapshot_mutation_size_and_validation(
    tmp_path: Path,
) -> None:
    hooks = RecordingHooks()
    engine = _engine(tmp_path, hooks)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "notes.md").write_text("old")

    engine.write_text(
        WriteTextRequest(locator=locator, path="notes.md", content="new text")
    )

    assert hooks.events == [
        "barrier-enter:write",
        "quota:5",
        "snapshot:notes.md:write",
        "size:5",
        "validate:write:notes.md",
        "barrier-exit:write",
        "invalidate:write:notes.md",
    ]


def test_validation_failure_skips_invalidation(tmp_path: Path) -> None:
    hooks = RecordingHooks(fail_validation=True)
    engine = _engine(tmp_path, hooks)
    locator = FileLocator(domain="test", resource_id="workspace")

    with pytest.raises(FileCoreError) as exc:
        engine.write_text(
            WriteTextRequest(locator=locator, path="pkg/manifest.json", content="{}")
        )

    assert exc.value.code == "VALIDATION_FAILED"
    assert not any(event.startswith("invalidate:") for event in hooks.events)
    assert hooks.events[-1] == "barrier-exit:write"


def test_copy_locks_source_and_destination_before_barrier(tmp_path: Path) -> None:
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "source.txt").write_text("hello")
    adapter = RootedFileAdapter(root_resolver=StaticRootResolver(tmp_path))
    lock_manager = ResourceWriteLockManager()
    hooks = LockInspectingHooks(
        lock_manager,
        expected_keys=[
            adapter.lock_key_for(locator, "source.txt", "copy"),
            adapter.lock_key_for(locator, "copy.txt", "copy"),
        ],
    )
    engine = FileOperationEngine(
        adapter=adapter,
        policy=FilePolicy(max_read_bytes=1024, max_write_bytes=1024),
        hooks=hooks,
        write_locks=lock_manager,
    )

    engine.copy_entry(
        CopyEntryRequest(locator=locator, source_path="source.txt", dest_path="copy.txt")
    )

    assert hooks.events[0] == "barrier-enter:copy"


def test_sync_tree_has_single_mutation_boundary(tmp_path: Path) -> None:
    hooks = RecordingHooks()
    engine = _engine(tmp_path, hooks)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "existing.txt").write_text("old")
    (tmp_path / "stale.txt").write_text("remove")

    result = engine.sync_tree(
        SyncTreeRequest(
            locator=locator,
            files=[
                SyncTreeItem(path="existing.txt", content=b"new content"),
                SyncTreeItem(path="created.txt", content=b"created"),
            ],
        )
    )

    assert result.failed == 0
    assert result.succeeded == 3
    assert hooks.events.count("barrier-enter:sync") == 1
    assert hooks.events.count("barrier-exit:sync") == 1
    validate_events = [
        event for event in hooks.events if event.startswith("validate:sync:")
    ]
    invalidate_events = [
        event for event in hooks.events if event.startswith("invalidate:sync:")
    ]
    assert len(validate_events) == 1
    assert len(invalidate_events) == 1
    assert set(validate_events[0].split(":", 2)[2].split(",")) == {
        "existing.txt",
        "created.txt",
        "stale.txt",
    }
    assert set(invalidate_events[0].split(":", 2)[2].split(",")) == {
        "existing.txt",
        "created.txt",
        "stale.txt",
    }


def test_delete_directory_snapshots_each_file_before_mutation(tmp_path: Path) -> None:
    hooks = RecordingHooks()
    engine = _engine(tmp_path, hooks)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "docs/nested").mkdir(parents=True)
    (tmp_path / "docs/readme.md").write_text("readme")
    (tmp_path / "docs/nested/guide.md").write_text("guide")

    engine.delete_entry(
        DeleteEntryRequest(locator=locator, path="docs", recursive=True)
    )

    assert "snapshot:docs/readme.md:delete" in hooks.events
    assert "snapshot:docs/nested/guide.md:delete" in hooks.events
    assert "snapshot:docs:delete" not in hooks.events
