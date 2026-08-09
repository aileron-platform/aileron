from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, FrozenSet, Iterable, Literal, Optional, Sequence

from .versioning import ContentHashVersionStrategy, VersionStrategy


DEFAULT_EXCLUDED_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        ".next",
    }
)


@dataclass(frozen=True)
class FileReadPolicy:
    binary_mode: Literal["friendly-text", "error"] = "error"
    large_file_mode: Literal["friendly-text", "error", "truncate"] = "error"
    truncate_after_lines: Optional[int] = None
    fallback_encodings: Sequence[str] = ()
    friendly_binary_message: Optional[str] = None
    friendly_large_message: Optional[str] = None


@dataclass(frozen=True)
class FileArchivePolicy:
    max_selected_roots: int = 100
    max_entries: int = 5000
    max_total_bytes: int = 250 * 1024 * 1024


@dataclass(frozen=True)
class PathExclusionPolicy:
    excluded_names: FrozenSet[str] = field(
        default_factory=lambda: frozenset(DEFAULT_EXCLUDED_NAMES)
    )
    predicate: Optional[Callable[[Path], bool]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "excluded_names", frozenset(self.excluded_names))

    @classmethod
    def defaults(cls, extra_names: Iterable[str] = ()) -> "PathExclusionPolicy":
        names = set(DEFAULT_EXCLUDED_NAMES)
        names.update(extra_names)
        return cls(excluded_names=frozenset(names))

    def is_excluded(self, relative_path: Path) -> bool:
        path = Path(relative_path)
        if self.predicate is not None and self.predicate(path):
            return True
        return any(part in self.excluded_names for part in path.parts)


@dataclass(frozen=True)
class FilePolicy:
    max_read_bytes: int
    max_write_bytes: int
    max_upload_files: int = 50
    max_extract_entries: int = 1000
    max_extract_entry_bytes: int = 20 * 1024 * 1024
    max_extract_total_bytes: int = 100 * 1024 * 1024
    max_archive_selected_roots: int = 100
    max_archive_entries: int = 5000
    max_archive_total_bytes: int = 250 * 1024 * 1024
    max_search_file_bytes: int = 1 * 1024 * 1024
    max_search_results: int = 100
    include_hidden_default: bool = False
    preserve_copy_metadata: bool = False
    cleanup_empty_parents: bool = False
    directory_destination_mode: Literal["append-source-name", "treat-as-target"] = (
        "append-source-name"
    )
    read_policy: FileReadPolicy = field(default_factory=FileReadPolicy)
    archive_policy: FileArchivePolicy | None = None
    version_strategy: VersionStrategy = field(
        default_factory=ContentHashVersionStrategy
    )
    path_exclusion: PathExclusionPolicy = field(
        default_factory=PathExclusionPolicy.defaults
    )

    def __post_init__(self) -> None:
        if self.archive_policy is None:
            object.__setattr__(
                self,
                "archive_policy",
                FileArchivePolicy(
                    max_selected_roots=self.max_archive_selected_roots,
                    max_entries=self.max_archive_entries,
                    max_total_bytes=self.max_archive_total_bytes,
                ),
            )
