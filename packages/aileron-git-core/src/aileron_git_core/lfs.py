from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Iterable, Mapping, Tuple

from .command_runner import git_allow_failure, run_git
from .errors import VersionControlError
from .models import LfsPatterns


_ATTR_SUFFIX = "filter=lfs diff=lfs merge=lfs -text"

DEFAULT_LFS_PATTERNS = (
    "*.pdf",
    "*.zip",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.pptx",
    "*.docx",
    "*.xlsx",
)


def read_patterns(repo_root: Path) -> LfsPatterns:
    attributes = repo_root / ".gitattributes"
    if not attributes.exists():
        return LfsPatterns(patterns=())
    patterns = []
    for raw_line in attributes.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pattern, separator, attributes_text = line.partition(" ")
        if separator and all(
            token in attributes_text.split()
            for token in ("filter=lfs", "diff=lfs", "merge=lfs", "-text")
        ):
            patterns.append(pattern)
    return LfsPatterns(patterns=tuple(patterns))


def update_patterns(repo_root: Path, patterns: Iterable[str]) -> LfsPatterns:
    normalized = tuple(dict.fromkeys(_validate_pattern(value) for value in patterns))
    attributes = repo_root / ".gitattributes"
    preserved = []
    if attributes.exists():
        for raw_line in attributes.read_text(encoding="utf-8").splitlines():
            if not _is_lfs_line(raw_line):
                preserved.append(raw_line)
    lines = preserved + [f"{pattern} {_ATTR_SUFFIX}" for pattern in normalized]
    content = "\n".join(lines)
    attributes.write_text(f"{content}\n" if content else "", encoding="utf-8")
    return LfsPatterns(patterns=normalized)


def preview_snapshot(
    repo_root: Path,
    patterns: Iterable[str],
    *,
    sample_limit: int = 100,
) -> tuple[int, int, Tuple[str, ...]]:
    normalized = tuple(_validate_pattern(value) for value in patterns)
    matches: list[tuple[str, int]] = []
    for candidate in repo_root.rglob("*"):
        if (
            candidate.is_symlink()
            or not candidate.is_file()
            or ".git" in candidate.parts
        ):
            continue
        relative = candidate.relative_to(repo_root).as_posix()
        if relative == ".gitattributes":
            continue
        if any(
            fnmatch(relative, pattern) or fnmatch(candidate.name, pattern)
            for pattern in normalized
        ):
            matches.append((relative, candidate.stat().st_size))
    matches.sort(key=lambda item: item[0])
    return (
        len(matches),
        sum(size for _, size in matches),
        tuple(path for path, _ in matches[:sample_limit]),
    )


def convert_snapshot(
    repo_root: Path,
    paths: Iterable[str],
    *,
    progress: Callable[[int, int], None] | None = None,
    is_cancel_requested: Callable[[], bool] | None = None,
    environment: Mapping[str, str] | None = None,
) -> Tuple[str, ...]:
    normalized = tuple(paths)
    if git_allow_failure(repo_root, "lfs", "version", env=environment).returncode != 0:
        raise VersionControlError("lfs_unavailable")
    total = len(normalized)
    if progress:
        progress(0, total)
    converted = []
    for path in normalized:
        if is_cancel_requested and is_cancel_requested():
            raise VersionControlError("operation_cancelled")
        run_git(repo_root, "add", "--renormalize", "--", path, env=environment)
        converted.append(path)
        if progress:
            progress(len(converted), total)
    if is_cancel_requested and is_cancel_requested():
        raise VersionControlError("operation_cancelled")
    return tuple(converted)


def _validate_pattern(pattern: str) -> str:
    value = pattern.strip()
    if not value or any(character.isspace() for character in value) or value.startswith("-"):
        raise VersionControlError("lfs_pattern_invalid")
    return value


def _is_lfs_line(line: str) -> bool:
    return all(
        token in line.split()
        for token in ("filter=lfs", "diff=lfs", "merge=lfs", "-text")
    )
