"""Claude Code module shared utilities"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple

import yaml

from app.config.settings import get_workspace_path


class DocumentScope(str, Enum):
    """Supported configuration file scopes"""

    PROJECT = "project"
    USER = "user"
    LOCAL = "local"
    PLUGIN = "plugin"  # Added: Plugin scope


class DocumentNotFoundError(FileNotFoundError):
    """Specified file does not exist"""


class DuplicateDocumentError(FileExistsError):
    """File already exists"""


class AmbiguousDocumentError(RuntimeError):
    """Found multiple files with same name"""


class InvalidDocumentFileNameError(ValueError):
    """File name is unsafe or uses an unsupported extension"""


def utcnow() -> datetime:
    """Get current UTC time"""

    return datetime.now(timezone.utc)


BYTES_PER_KB = 1024


def humanize_size(byte_count: int) -> str:
    """Represent size in human-readable format (simplified version)"""

    if byte_count < BYTES_PER_KB:
        return f"{byte_count}B"
    kilobytes = byte_count / BYTES_PER_KB
    if kilobytes < BYTES_PER_KB:
        return f"{kilobytes:.0f}KB"
    megabytes = kilobytes / BYTES_PER_KB
    return f"{megabytes:.1f}MB"


def format_file_size(size_bytes: int) -> str:
    """Format file size (detailed version, supports more units)

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted file size string (e.g., "1.5KB", "2.3MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < BYTES_PER_KB:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= BYTES_PER_KB
    return f"{size_bytes:.1f}TB"


def parse_front_matter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse Markdown Front Matter"""

    if not content.startswith("---"):
        return {}, content

    parts = content.split("\n---", 1)
    if len(parts) != 2:
        return {}, content

    header = parts[0].replace("---", "", 1).strip()
    body = parts[1]
    try:
        metadata = yaml.safe_load(header) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, body.lstrip("\n")


def workspace_root() -> Path:
    """Get workspace root directory"""

    return Path(get_workspace_path())


def ensure_directory(path: Path) -> None:
    """Ensure directory exists"""

    path.mkdir(parents=True, exist_ok=True)


def resolve_scope_root(workspace_id: str, scope: DocumentScope) -> Path:
    """Get corresponding .claude root directory path based on scope

    Args:
        workspace_id: Workspace ID (reserved parameter for API compatibility, not actually used)
        scope: Document scope type

    Returns:
        Path: USER scope returns .claude in developer user home, other scopes return .claude in workspace root
    """
    return Path("/home/developer/.claude") if scope == DocumentScope.USER else workspace_root() / ".claude"


def read_json_file(file_path: Path) -> Dict[str, Any]:
    """Read JSON configuration file, return empty dict if file doesn't exist or format is incorrect"""

    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json_file(file_path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON configuration file and ensure directory exists"""

    ensure_directory(file_path.parent)
    file_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@dataclass(init=False)
class MarkdownDocumentRecord:
    """Markdown configuration file content"""

    file_path: Path
    root_path: Path
    scope: DocumentScope
    content: str
    metadata: Dict[str, Any]
    size_bytes: int
    updated_at: datetime | None
    _explicit_namespace: str | None
    _explicit_size_label: str | None

    def __init__(
        self,
        *,
        file_path: str | Path,
        root_path: str | Path | None = None,
        scope: DocumentScope,
        content: str,
        metadata: Dict[str, Any] | None = None,
        size_bytes: int = 0,
        updated_at: datetime | None = None,
        file_name: str | None = None,
        namespace: str | None = None,
        size_label: str | None = None,
    ) -> None:
        path_obj = Path(file_path)
        if file_name and path_obj.name != file_name:
            path_obj = path_obj.parent / file_name

        if root_path is None:
            if namespace:
                root_obj = path_obj.parent.parent
            else:
                root_obj = path_obj.parent
        else:
            root_obj = Path(root_path)

        self.file_path = path_obj
        self.root_path = root_obj
        self.scope = scope
        self.content = content
        self.metadata = metadata or {}
        self.size_bytes = size_bytes
        self.updated_at = updated_at
        self._explicit_namespace = namespace
        self._explicit_size_label = size_label

    @property
    def file_name(self) -> str:
        return self.file_path.name  # Keep complete extension (including .md)

    @property
    def namespace(self) -> str:
        if self._explicit_namespace is not None:
            return self._explicit_namespace
        try:
            relative = self.file_path.parent.relative_to(self.root_path)
        except ValueError:
            return ""
        if str(relative) == ".":
            return ""
        return str(relative).replace("\\", "/")

    @property
    def size_label(self) -> str:
        if self._explicit_size_label is not None:
            return self._explicit_size_label
        return humanize_size(self.size_bytes)

    def metadata_with_fallbacks(
        self,
        *,
        fallback_name: str | None = None,
        fallback_description: str | None = None,
        fallback_namespace: str | None = None,
    ) -> Dict[str, Any]:
        metadata = dict(self.metadata)
        if "name" not in metadata and fallback_name:
            metadata["name"] = fallback_name
        if "description" not in metadata and fallback_description:
            metadata["description"] = fallback_description
        namespace = metadata.get("namespace") or metadata.get("category")
        if not namespace:
            namespace = fallback_namespace or self.namespace
            if namespace:
                metadata["namespace"] = namespace
        return metadata


class ScopedMarkdownRepository:
    """Handle scope-stored Markdown files"""

    def __init__(
        self,
        folder_name: str,
        *,
        supports_namespace: bool = False,
        scope_root_resolver: Callable[[str, DocumentScope], Path] | None = None,
    ) -> None:
        self.folder_name = folder_name
        self.supports_namespace = supports_namespace
        self._scope_root_resolver = scope_root_resolver

    # Directory & Path ---------------------------------------------
    def _directory(self, workspace_id: str, scope: DocumentScope) -> Path:
        root = self._scope_root_resolver(workspace_id, scope) if self._scope_root_resolver else resolve_scope_root(workspace_id, scope)
        return root / self.folder_name

    def _namespace_directory(self, directory: Path, namespace: str | None) -> Path:
        if not namespace:
            return directory
        return directory / namespace

    def _normalize_file_name(self, file_name: str) -> str:
        clean_name = file_name.strip()
        path = Path(clean_name)
        if (
            not clean_name
            or path.is_absolute()
            or ".." in path.parts
            or "/" in clean_name
            or "\\" in clean_name
            or (path.suffix and path.suffix.lower() != ".md")
        ):
            raise InvalidDocumentFileNameError(file_name)
        if clean_name.endswith(".md"):
            return clean_name
        return f"{clean_name}.md"

    def _load_record(
        self, file_path: Path, scope: DocumentScope, directory: Path
    ) -> MarkdownDocumentRecord:
        content = file_path.read_text(encoding="utf-8")
        metadata, _ = parse_front_matter(content)
        stat = file_path.stat()
        return MarkdownDocumentRecord(
            file_path=file_path,
            root_path=directory,
            scope=scope,
            content=content,
            metadata=metadata,
            size_bytes=stat.st_size,
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        )

    # Public Operations -------------------------------------------
    def list_records(
        self, workspace_id: str, scope: DocumentScope
    ) -> List[MarkdownDocumentRecord]:
        directory = self._directory(workspace_id, scope)
        if not directory.exists():
            return []
        records: List[MarkdownDocumentRecord] = []
        for file_path in sorted(directory.rglob("*.md")):
            records.append(self._load_record(file_path, scope, directory))
        return records

    def get_record(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        *,
        namespace: str | None = None,
    ) -> MarkdownDocumentRecord:
        directory = self._directory(workspace_id, scope)
        file_path = self._resolve_file_path(directory, file_name, namespace=namespace)
        if file_path is None or not file_path.exists():
            raise DocumentNotFoundError(file_name)
        return self._load_record(file_path, scope, directory)

    def create_record(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        content: str,
        *,
        namespace: str | None = None,
    ) -> MarkdownDocumentRecord:
        directory = self._directory(workspace_id, scope)
        target_dir = self._namespace_directory(directory, namespace)
        ensure_directory(target_dir)
        normalized_name = self._normalize_file_name(file_name)
        file_path = target_dir / normalized_name
        if file_path.exists():
            raise DuplicateDocumentError(file_name)
        file_path.write_text(content, encoding="utf-8")
        return self._load_record(file_path, scope, directory)

    def update_record(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        content: str,
        *,
        namespace: str | None = None,
    ) -> MarkdownDocumentRecord:
        directory = self._directory(workspace_id, scope)
        file_path = self._resolve_file_path(directory, file_name, namespace=namespace)
        if file_path is None or not file_path.exists():
            raise DocumentNotFoundError(file_name)
        file_path.write_text(content, encoding="utf-8")
        return self._load_record(file_path, scope, directory)

    def delete_record(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        *,
        namespace: str | None = None,
    ) -> None:
        directory = self._directory(workspace_id, scope)
        file_path = self._resolve_file_path(directory, file_name, namespace=namespace)
        if file_path is None or not file_path.exists():
            raise DocumentNotFoundError(file_name)
        file_path.unlink()

    # Internal Utilities -------------------------------------------
    def _resolve_file_path(
        self, directory: Path, file_name: str, *, namespace: str | None
    ) -> Path | None:
        normalized_name = self._normalize_file_name(file_name)
        if namespace:
            candidate = directory / namespace / normalized_name
            if candidate.exists():
                return candidate
            return None
        candidates = [
            path
            for path in directory.rglob("*.md")
            if path.stem == Path(normalized_name).stem
        ]
        if not candidates:
            return None
        if len(candidates) > 1 and namespace is None:
            raise AmbiguousDocumentError(file_name)
        return candidates[0]


def iter_requested_scopes(
    scope: DocumentScope | None, *, allow_local: bool = True, allow_plugin: bool = False
) -> Iterable[DocumentScope]:
    """Get scopes to process based on query parameters

    Args:
        scope: Specified scope, if None returns all supported scopes
        allow_local: Whether to include LOCAL scope (default True)
        allow_plugin: Whether to include PLUGIN scope (default False, as plugins usually need special handling)
    """

    if scope:
        return [scope]
    scopes: List[DocumentScope] = [DocumentScope.PROJECT, DocumentScope.USER]
    if allow_local:
        scopes.append(DocumentScope.LOCAL)
    if allow_plugin:
        scopes.append(DocumentScope.PLUGIN)
    return scopes


def check_scope_writable(scope: DocumentScope) -> None:
    """Check if scope is writable, raise exception if PLUGIN scope

    Args:
        scope: Scope to check

    Raises:
        ValueError: If scope is PLUGIN (read-only)
    """
    if scope == DocumentScope.PLUGIN:
        raise ValueError("Plugin scope is read-only. Plugins can only be managed through the marketplace.")
