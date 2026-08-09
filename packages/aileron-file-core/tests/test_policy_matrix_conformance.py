from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from aileron_file_core import (
    BatchWriteItem,
    BatchWriteRequest,
    ExtractArchiveRequest,
    FileLocator,
    FileMutationHooks,
    FileOperationEngine,
    FilePolicy,
    PathExclusionPolicy,
    RootedFileAdapter,
    SearchRequest,
    ScopedRootResolver,
    StaticRootResolver,
    UploadFilesRequest,
    UploadItem,
)


@dataclass(frozen=True)
class DomainCase:
    name: str
    policy: FilePolicy
    scope: str | None = None
    provider: str | None = None
    package_id: str | None = None


DOMAIN_CASES = (
    DomainCase(
        name="workspace",
        policy=FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024 * 1024,
            path_exclusion=PathExclusionPolicy.defaults(extra_names={"node_modules"}),
        ),
        scope="workspace",
    ),
    DomainCase(
        name="knowledge-base",
        policy=FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024 * 1024,
            preserve_copy_metadata=True,
            directory_destination_mode="treat-as-target",
            path_exclusion=PathExclusionPolicy.defaults(extra_names={"__derived__"}),
        ),
    ),
    DomainCase(
        name="marketplace-registry",
        policy=FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024 * 1024,
            path_exclusion=PathExclusionPolicy.defaults(extra_names={".marketplace"}),
        ),
    ),
    DomainCase(
        name="marketplace-package",
        policy=FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024 * 1024,
            path_exclusion=PathExclusionPolicy.defaults(extra_names={".marketplace"}),
        ),
        provider="codex",
        package_id="demo",
    ),
)


@dataclass
class RecordingHooks(FileMutationHooks):
    snapshots: list[tuple[str, str]] = field(default_factory=list)
    invalidations: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    @contextmanager
    def write_barrier(self, locator: FileLocator, operation: str):
        _ = (locator, operation)
        yield

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        _ = (locator, absolute_path)
        self.snapshots.append((operation, relative_path))

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def validate_after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: list[str],
    ) -> None:
        _ = (locator, operation, paths)

    def after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: list[str],
    ) -> None:
        _ = locator
        self.invalidations.append((operation, tuple(paths)))


def _engine(root: Path, domain_case: DomainCase) -> FileOperationEngine:
    if domain_case.scope is not None:
        root_resolver = ScopedRootResolver(
            roots={domain_case.scope: root},
            default_scope=domain_case.scope,
        )
    else:
        root_resolver = StaticRootResolver(root)
    return FileOperationEngine(
        adapter=RootedFileAdapter(
            root_resolver=root_resolver,
            path_exclusion=domain_case.policy.path_exclusion,
        ),
        policy=domain_case.policy,
        hooks=RecordingHooks(),
    )


def _zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buffer.getvalue()


@pytest.mark.parametrize("domain_case", DOMAIN_CASES, ids=lambda case: case.name)
def test_upload_extract_search_and_batch_share_core_behavior(
    tmp_path: Path,
    domain_case: DomainCase,
) -> None:
    engine = _engine(tmp_path, domain_case)
    locator = FileLocator(
        domain=domain_case.name,
        resource_id="resource",
        scope=domain_case.scope,
        provider=domain_case.provider,
        package_id=domain_case.package_id,
    )

    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "notes.md").write_text("old", encoding="utf-8")
    upload = engine.upload_files(
        UploadFilesRequest(
            locator=locator,
            target_path="/uploads",
            files=[UploadItem(filename="notes.md", content=b"new")],
            default_strategy="replace",
        )
    )
    extract = engine.extract_archive(
        ExtractArchiveRequest(
            locator=locator,
            target_path="/uploads",
            archive_name="docs.zip",
            archive_bytes=_zip_bytes({"docs/readme.md": "Alpha topic"}),
            default_strategy="replace",
        )
    )
    search = engine.search(SearchRequest(locator=locator, query="alpha"))
    batch = engine.batch_write(
        BatchWriteRequest(
            locator=locator,
            files=[BatchWriteItem(path="batch/result.txt", content="ok")],
        )
    )

    assert upload.items[0].final_path == "uploads/notes.md"
    assert extract.items[0].final_path == "uploads/docs/readme.md"
    assert search.matches[0].path == "uploads/docs/readme.md"
    assert batch.succeeded == 1
    assert isinstance(engine.hooks, RecordingHooks)
    assert ("upload", "uploads/notes.md") in engine.hooks.snapshots
    assert engine.hooks.invalidations
