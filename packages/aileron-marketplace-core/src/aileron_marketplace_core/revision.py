from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def _iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return sorted(item for item in root.rglob("*") if item.is_file())


def _file_content_digest(file_path: Path) -> bytes:
    return sha256(file_path.read_bytes()).digest()


def revision_for_package_paths(paths: list[Path]) -> str:
    digest = sha256()
    for root in paths:
        for file_path in _iter_files(root):
            relative = file_path.name if root.is_file() else str(file_path.relative_to(root))
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(_file_content_digest(file_path))
            digest.update(b"\0")
    return digest.hexdigest()
