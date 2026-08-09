from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, BinaryIO, Mapping, Optional, Sequence


@dataclass(frozen=True)
class FileLocator:
    domain: str
    resource_id: str
    scope: Optional[str] = None
    provider: Optional[str] = None
    package_id: Optional[str] = None


@dataclass(frozen=True)
class TreeRequest:
    locator: FileLocator
    path: str = "/"
    include_hidden: bool = False
    max_depth: int = 1


@dataclass(frozen=True)
class ReadTextRequest:
    locator: FileLocator
    path: str


@dataclass(frozen=True)
class ReadBytesRequest:
    locator: FileLocator
    path: str


@dataclass(frozen=True)
class WriteTextRequest:
    locator: FileLocator
    path: str
    content: str
    expected_version_id: Optional[str] = None
    encoding: str = "utf-8"


@dataclass(frozen=True)
class WriteBytesRequest:
    locator: FileLocator
    path: str
    content: bytes
    operation: str = "write"
    expected_version_id: Optional[str] = None


@dataclass(frozen=True)
class CreateEntryRequest:
    locator: FileLocator
    path: str
    entry_type: str
    content: str = ""
    encoding: str = "utf-8"


@dataclass(frozen=True)
class DeleteEntryRequest:
    locator: FileLocator
    path: str
    recursive: bool = False


@dataclass(frozen=True)
class MoveEntryRequest:
    locator: FileLocator
    source_path: str
    dest_path: str
    source_locator: Optional[FileLocator] = None
    dest_locator: Optional[FileLocator] = None


@dataclass(frozen=True)
class CopyEntryRequest:
    locator: FileLocator
    source_path: str
    dest_path: str
    source_locator: Optional[FileLocator] = None
    dest_locator: Optional[FileLocator] = None


@dataclass(frozen=True)
class FileConflictResolution:
    source_path: str
    strategy: str


@dataclass(frozen=True)
class FileConflictItem:
    source_path: str
    target_path: str
    source_type: str
    target_type: str
    can_replace: bool


@dataclass(frozen=True)
class FileConflictPreflight:
    conflicts: Sequence[FileConflictItem]
    total: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflicts", tuple(self.conflicts))


@dataclass(frozen=True)
class CopyEntriesRequest:
    locator: FileLocator
    source_paths: Sequence[str]
    target_path: str
    default_strategy: str = "cancel"
    resolutions: Sequence[FileConflictResolution] = ()
    source_locator: Optional[FileLocator] = None
    dest_locator: Optional[FileLocator] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_paths", tuple(self.source_paths))
        object.__setattr__(self, "resolutions", tuple(self.resolutions))


@dataclass(frozen=True)
class UploadItem:
    filename: str
    content: bytes


@dataclass(frozen=True)
class UploadStreamItem:
    filename: str
    stream: BinaryIO
    size: int


@dataclass(frozen=True)
class UploadFilesRequest:
    locator: FileLocator
    target_path: str
    files: Sequence[UploadItem]
    default_strategy: str = "cancel"
    resolutions: Sequence[FileConflictResolution] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(self.files))
        object.__setattr__(self, "resolutions", tuple(self.resolutions))


@dataclass(frozen=True)
class ExtractArchiveRequest:
    locator: FileLocator
    target_path: str
    archive_name: str
    archive_bytes: bytes
    default_strategy: str = "cancel"
    resolutions: Sequence[FileConflictResolution] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolutions", tuple(self.resolutions))


@dataclass(frozen=True)
class ExtractArchiveStreamRequest:
    locator: FileLocator
    target_path: str
    archive_name: str
    archive_stream: BinaryIO
    archive_size: int
    default_strategy: str = "cancel"
    resolutions: Sequence[FileConflictResolution] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolutions", tuple(self.resolutions))


@dataclass(frozen=True)
class BuildArchiveRequest:
    locator: FileLocator
    paths: Sequence[str]
    archive_root: str = ""
    extra_entries: Sequence["ArchiveMemoryEntry"] = ()
    reject_symlinks: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", tuple(self.paths))
        object.__setattr__(self, "extra_entries", tuple(self.extra_entries))


@dataclass(frozen=True)
class SearchRequest:
    locator: FileLocator
    query: str
    path: str = "/"
    include_content: bool = True
    case_sensitive: bool = False
    max_results: Optional[int] = None


@dataclass(frozen=True)
class ListFilesRequest:
    locator: FileLocator
    path: str = "/"
    include_content: bool = False
    include_hidden: bool = False


@dataclass(frozen=True)
class BatchDeleteRequest:
    locator: FileLocator
    paths: Sequence[str]
    recursive: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", tuple(self.paths))


@dataclass(frozen=True)
class BatchWriteItem:
    path: str
    content: str
    expected_version_id: Optional[str] = None
    encoding: str = "utf-8"


@dataclass(frozen=True)
class BatchWriteRequest:
    locator: FileLocator
    files: Sequence[BatchWriteItem]

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(self.files))


@dataclass(frozen=True)
class SyncTreeItem:
    path: str
    content: bytes


@dataclass(frozen=True)
class SyncTreeRequest:
    locator: FileLocator
    files: Sequence[SyncTreeItem]
    delete_missing: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(self.files))


@dataclass(frozen=True)
class FileTreeNode:
    name: str
    path: str
    type: str
    size: int
    updated_at: str
    depth: int
    children: Sequence["FileTreeNode"] = field(default_factory=tuple)
    has_children: bool = False
    extension: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class FileTree:
    path: str
    nodes: Sequence[FileTreeNode]
    total: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))


@dataclass(frozen=True)
class FileContent:
    path: str
    content: str
    size: int
    updated_at: str
    version_id: str
    content_hash: Optional[str] = None
    readable: bool = True
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class FileBytes:
    path: str
    content: bytes
    size: int
    updated_at: str


@dataclass(frozen=True)
class FileListItem:
    path: str
    name: str
    size: int
    updated_at: str
    content: Optional[str] = None
    content_encoding: Optional[str] = None
    binary: bool = False


@dataclass(frozen=True)
class FileList:
    items: Sequence[FileListItem]
    total: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True)
class FileMutationResult:
    path: str
    operation: str
    entry_type: str
    size: int = 0
    version_id: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class UploadItemResult:
    source_path: str
    final_path: Optional[str]
    status: str
    size: int
    error: Optional[str] = None
    updated_at: Optional[str] = None
    entry_type: str = "file"


@dataclass(frozen=True)
class UploadBatchResult:
    items: Sequence[UploadItemResult]
    total: int
    succeeded: int
    skipped: int
    failed: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True)
class ArchiveEntry:
    fs_path: str
    archive_path: str
    size: int


@dataclass(frozen=True)
class ArchiveMemoryEntry:
    archive_path: str
    content: bytes


@dataclass(frozen=True)
class ArchiveBuildResult:
    entries: Sequence[ArchiveEntry]
    selected_paths: Sequence[str]
    total_size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "selected_paths", tuple(self.selected_paths))


@dataclass(frozen=True)
class ArchiveBytesResult:
    content: bytes
    entries: Sequence[ArchiveEntry]
    selected_paths: Sequence[str]
    total_size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "selected_paths", tuple(self.selected_paths))


@dataclass(frozen=True)
class SearchMatch:
    path: str
    name: str
    entry_type: str
    size: int
    updated_at: str
    match_type: str
    line: Optional[int] = None
    preview: Optional[str] = None


@dataclass(frozen=True)
class SearchResult:
    matches: Sequence[SearchMatch]
    total: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "matches", tuple(self.matches))


@dataclass(frozen=True)
class BatchItemResult:
    path: str
    status: str
    size: Optional[int] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class BatchMutationResult:
    results: Sequence[BatchItemResult]
    total: int
    succeeded: int
    failed: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", tuple(self.results))


def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).astimezone().isoformat()
