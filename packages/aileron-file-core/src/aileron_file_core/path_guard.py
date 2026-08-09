from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import PathOutsideRootError


@dataclass(frozen=True)
class SafePath:
    root: Path
    relative_path: str
    absolute_path: Path


def resolve_safe_path(root: Path, requested_path: str) -> SafePath:
    resolved_root = root.resolve()
    normalized = _normalize_relative_path(requested_path)
    absolute_path = (resolved_root / normalized).resolve()
    if absolute_path != resolved_root and resolved_root not in absolute_path.parents:
        raise PathOutsideRootError(requested_path)
    return SafePath(
        root=resolved_root,
        relative_path=normalized,
        absolute_path=absolute_path,
    )


def _normalize_relative_path(requested_path: str) -> str:
    value = requested_path.replace("\\", "/")
    if value in ("", "."):
        return "."
    if value.startswith("/"):
        raise PathOutsideRootError(requested_path)
    parts: list[str] = []
    for part in PurePosixPath(value).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise PathOutsideRootError(requested_path)
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts) if parts else "."
