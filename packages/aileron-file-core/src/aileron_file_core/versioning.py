from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Optional, Protocol

from .errors import VersionConflictError


class VersionStrategy(Protocol):
    def read_version(self, path: Path) -> str:
        """Return an opaque version token for the path."""


@dataclass(frozen=True)
class ContentHashVersionStrategy:
    length: Optional[int] = None

    def read_version(self, path: Path) -> str:
        hasher = sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        return digest[: self.length] if self.length else digest


@dataclass(frozen=True)
class MTimeVersionStrategy:
    prefix: str = "v"

    def read_version(self, path: Path) -> str:
        return f"{self.prefix}{path.stat().st_mtime_ns}"


@dataclass(frozen=True)
class WriteResult:
    path: Path
    version_id: str
    size: int


def compare_and_write_text(
    path: Path,
    content: str,
    *,
    expected_version_id: Optional[str],
    strategy: VersionStrategy,
    encoding: str = "utf-8",
) -> WriteResult:
    if path.exists() and expected_version_id is not None:
        actual_version = strategy.read_version(path)
        if actual_version != expected_version_id:
            raise VersionConflictError(str(path), expected_version_id, actual_version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)
    return WriteResult(
        path=path,
        version_id=strategy.read_version(path),
        size=path.stat().st_size,
    )
