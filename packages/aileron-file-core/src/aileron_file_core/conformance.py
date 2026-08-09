from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Iterator, Sequence
from zipfile import ZipFile

from .engine import FileOperationEngine
from .errors import FileCoreError
from .hooks import FileMutationHooks
from .models import (
    CopyEntryRequest,
    DeleteEntryRequest,
    ExtractArchiveRequest,
    FileLocator,
    ListFilesRequest,
    MoveEntryRequest,
    ReadTextRequest,
    TreeRequest,
    UploadFilesRequest,
    UploadItem,
    WriteTextRequest,
)


def assert_engine_conformance(
    *,
    engine: FileOperationEngine,
    locator: FileLocator,
    base_path: str = "conformance",
) -> None:
    original_hooks = engine.hooks
    recorder = _RecordingHookProxy(original_hooks)
    engine.hooks = recorder
    try:
        engine.write_text(
            WriteTextRequest(
                locator=locator,
                path=f"{base_path}/readme.md",
                content="alpha",
            )
        )
        content = engine.read_text(
            ReadTextRequest(locator=locator, path=f"{base_path}/readme.md")
        )
        assert content.content == "alpha"

        hidden_path = engine.adapter.root_for(locator) / base_path / ".git" / "config"
        hidden_path.parent.mkdir(parents=True, exist_ok=True)
        hidden_path.write_text("hidden", encoding="utf-8")
        tree = engine.get_tree(
            TreeRequest(
                locator=locator, path=base_path, include_hidden=False, max_depth=3
            )
        )
        assert ".git" not in {node.name for node in tree.nodes}

        _assert_file_core_error(
            "CONTENT_CONFLICT",
            lambda: engine.write_text(
                WriteTextRequest(
                    locator=locator,
                    path=f"{base_path}/readme.md",
                    content="stale",
                    expected_version_id="stale-version",
                )
            ),
        )
        _assert_file_core_error(
            "PATH_OUTSIDE_ROOT",
            lambda: engine.write_text(
                WriteTextRequest(
                    locator=locator,
                    path="../escape.txt",
                    content="escape",
                )
            ),
        )

        upload_result = engine.upload_files(
            UploadFilesRequest(
                locator=locator,
                target_path=base_path,
                files=[UploadItem(filename="readme.md", content=b"beta")],
                default_strategy="keep-both",
            )
        )
        assert upload_result.succeeded == 1
        assert upload_result.items[0].final_path == f"{base_path}/readme_1.md"
        overwrite_result = engine.upload_files(
            UploadFilesRequest(
                locator=locator,
                target_path=base_path,
                files=[UploadItem(filename="readme.md", content=b"gamma")],
                default_strategy="replace",
            )
        )
        assert overwrite_result.items[0].final_path == f"{base_path}/readme.md"
        assert engine.read_text(
            ReadTextRequest(locator=locator, path=f"{base_path}/readme.md")
        ).content == "gamma"
        skipped_result = engine.upload_files(
            UploadFilesRequest(
                locator=locator,
                target_path=base_path,
                files=[UploadItem(filename="readme.md", content=b"skip")],
                default_strategy="skip",
            )
        )
        assert skipped_result.items[0].status == "skipped"

        _assert_file_core_error(
            "INVALID_ARCHIVE_ENTRY",
            lambda: engine.extract_archive(
                ExtractArchiveRequest(
                    locator=locator,
                    target_path=base_path,
                    archive_name="bad.zip",
                    archive_bytes=_zip_bytes({"../escape.txt": b"bad"}),
                )
            ),
        )

        engine.upload_files(
            UploadFilesRequest(
                locator=locator,
                target_path=f"{base_path}/assets",
                files=[UploadItem(filename="logo.bin", content=b"abc\x00def")],
                default_strategy="replace",
            )
        )
        listed = engine.list_files(
            ListFilesRequest(locator=locator, path=base_path, include_content=True)
        )
        by_path = {item.path: item for item in listed.items}
        assert by_path[f"{base_path}/readme.md"].content == "gamma"
        assert by_path[f"{base_path}/assets/logo.bin"].binary is True
        assert by_path[f"{base_path}/assets/logo.bin"].content_encoding == "base64"

        engine.copy_entry(
            CopyEntryRequest(
                locator=locator,
                source_path=f"{base_path}/readme.md",
                dest_path=f"{base_path}/copy.md",
            )
        )
        engine.move_entry(
            MoveEntryRequest(
                locator=locator,
                source_path=f"{base_path}/copy.md",
                dest_path=f"{base_path}/moved.md",
            )
        )
        assert engine.read_text(
            ReadTextRequest(locator=locator, path=f"{base_path}/moved.md")
        ).content == "gamma"
        engine.delete_entry(
            DeleteEntryRequest(locator=locator, path=f"{base_path}/moved.md")
        )
        _assert_file_core_error(
            "FILE_NOT_FOUND",
            lambda: engine.read_text(
                ReadTextRequest(locator=locator, path=f"{base_path}/moved.md")
            ),
        )

        _assert_event_order(
            recorder.events,
            [
                "barrier-enter:upload",
                "quota:0",
                f"snapshot:{base_path}/readme.md:upload",
                "size:0",
                f"validate:upload:{base_path}/readme.md",
                "barrier-exit:upload",
                f"invalidate:upload:{base_path}/readme.md",
            ],
        )
        _assert_event_order(
            recorder.events,
            [
                "barrier-enter:copy",
                "quota:5",
                "size:5",
                f"validate:copy:{base_path}/readme.md,{base_path}/copy.md",
                "barrier-exit:copy",
                f"invalidate:copy:{base_path}/readme.md,{base_path}/copy.md",
            ],
        )
        _assert_event_order(
            recorder.events,
            [
                "barrier-enter:move",
                "quota:0",
                f"snapshot:{base_path}/copy.md:move",
                "size:0",
                f"validate:move:{base_path}/copy.md,{base_path}/moved.md",
                "barrier-exit:move",
                f"invalidate:move:{base_path}/copy.md,{base_path}/moved.md",
            ],
        )
        _assert_event_order(
            recorder.events,
            [
                "barrier-enter:delete",
                "quota:-5",
                f"snapshot:{base_path}/moved.md:delete",
                "size:-5",
                f"validate:delete:{base_path}/moved.md",
                "barrier-exit:delete",
                f"invalidate:delete:{base_path}/moved.md",
            ],
        )
        assert any(event.startswith("quota:") for event in recorder.events)
        assert any(event.startswith("size:") for event in recorder.events)
    finally:
        engine.hooks = original_hooks


class _RecordingHookProxy(FileMutationHooks):
    def __init__(self, delegate: FileMutationHooks) -> None:
        self.delegate = delegate
        self.events: list[str] = []

    @contextmanager
    def write_barrier(self, locator: FileLocator, operation: str) -> Iterator[None]:
        self.events.append(f"barrier-enter:{operation}")
        with self.delegate.write_barrier(locator, operation):
            try:
                yield
            finally:
                self.events.append(f"barrier-exit:{operation}")

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        self.events.append(f"quota:{delta_bytes}")
        self.delegate.check_quota(locator, delta_bytes)

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        self.events.append(f"snapshot:{relative_path}:{operation}")
        self.delegate.snapshot_existing(locator, absolute_path, relative_path, operation)

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        self.events.append(f"size:{delta_bytes}")
        self.delegate.after_size_change(locator, delta_bytes)

    def validate_after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        self.events.append(f"validate:{operation}:{','.join(paths)}")
        self.delegate.validate_after_mutation(locator, operation, paths)

    def after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        self.events.append(f"invalidate:{operation}:{','.join(paths)}")
        self.delegate.after_mutation(locator, operation, paths)


def _assert_file_core_error(code: str, operation) -> None:
    try:
        operation()
    except FileCoreError as exc:
        assert exc.code == code
        return
    raise AssertionError(f"Expected FileCoreError({code})")


def _assert_event_order(events: Sequence[str], expected: Sequence[str]) -> None:
    cursor = 0
    for event in events:
        if event == expected[cursor]:
            cursor += 1
            if cursor == len(expected):
                return
    raise AssertionError(f"Expected event order {expected}, got {events}")


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()
