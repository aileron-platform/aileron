"""Claude Code 模組共用工具"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

from app.config.settings import get_workspace_path


class DocumentScope(str, Enum):
    """支援的設定檔案範圍"""

    PROJECT = "project"
    USER = "user"
    LOCAL = "local"
    PLUGIN = "plugin"  # 新增：Plugin 範圍


class DocumentNotFoundError(FileNotFoundError):
    """指定的檔案不存在"""


class DuplicateDocumentError(FileExistsError):
    """檔案已存在"""


class AmbiguousDocumentError(RuntimeError):
    """找到多個同名檔案"""


def utcnow() -> datetime:
    """取得 UTC 現在時間"""

    return datetime.now(timezone.utc)


BYTES_PER_KB = 1024


def humanize_size(byte_count: int) -> str:
    """以人類易讀格式表示大小（簡化版本）"""

    if byte_count < BYTES_PER_KB:
        return f"{byte_count}B"
    kilobytes = byte_count / BYTES_PER_KB
    if kilobytes < BYTES_PER_KB:
        return f"{kilobytes:.0f}KB"
    megabytes = kilobytes / BYTES_PER_KB
    return f"{megabytes:.1f}MB"


def format_file_size(size_bytes: int) -> str:
    """格式化檔案大小（詳細版本，支援更多單位）

    Args:
        size_bytes: 檔案大小（位元組）

    Returns:
        格式化後的檔案大小字串（例如: "1.5KB", "2.3MB"）
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < BYTES_PER_KB:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= BYTES_PER_KB
    return f"{size_bytes:.1f}TB"


def parse_front_matter(content: str) -> Tuple[Dict[str, Any], str]:
    """解析 Markdown Front Matter"""

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
    """取得工作區根目錄"""

    return Path(get_workspace_path())


def ensure_directory(path: Path) -> None:
    """確保目錄存在"""

    path.mkdir(parents=True, exist_ok=True)


def resolve_scope_root(workspace_id: str, scope: DocumentScope) -> Path:
    """根據 scope 取得對應的 .claude 根目錄路徑

    Args:
        workspace_id: 工作區 ID（保留參數以維持 API 相容性，實際未使用）
        scope: 文檔範圍類型

    Returns:
        Path: USER scope 回傳 developer 用戶家目錄的 .claude，其他 scope 回傳工作區根目錄的 .claude
    """
    return Path("/home/developer/.claude") if scope == DocumentScope.USER else workspace_root() / ".claude"


def read_json_file(file_path: Path) -> Dict[str, Any]:
    """讀取 JSON 設定檔，若檔案不存在或格式錯誤則回傳空 dict"""

    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json_file(file_path: Path, payload: Dict[str, Any]) -> None:
    """寫入 JSON 設定檔並確保目錄存在"""

    ensure_directory(file_path.parent)
    file_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@dataclass(init=False)
class MarkdownDocumentRecord:
    """Markdown 設定檔內容"""

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
        return self.file_path.name  # 保留完整附檔名（包含 .md）

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
    """處理依範圍儲存的 Markdown 檔案"""

    def __init__(self, folder_name: str, *, supports_namespace: bool = False) -> None:
        self.folder_name = folder_name
        self.supports_namespace = supports_namespace

    # 目錄與路徑 -----------------------------------------------------
    def _directory(self, workspace_id: str, scope: DocumentScope) -> Path:
        root = resolve_scope_root(workspace_id, scope)
        return root / self.folder_name

    def _namespace_directory(self, directory: Path, namespace: str | None) -> Path:
        if not namespace:
            return directory
        return directory / namespace

    def _normalize_file_name(self, file_name: str) -> str:
        if file_name.endswith(".md"):
            return file_name
        return f"{file_name}.md"

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

    # 公開操作 -------------------------------------------------------
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

    # 內部工具 -------------------------------------------------------
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
    """根據查詢參數取得要處理的範圍

    Args:
        scope: 指定的範圍，如果為 None 則返回所有支援的範圍
        allow_local: 是否包含 LOCAL scope（預設 True）
        allow_plugin: 是否包含 PLUGIN scope（預設 False，因為 plugin 通常需要特殊處理）
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
    """檢查 scope 是否可寫入，如果是 PLUGIN scope 則拋出異常

    Args:
        scope: 要檢查的範圍

    Raises:
        ValueError: 如果 scope 是 PLUGIN（只讀）
    """
    if scope == DocumentScope.PLUGIN:
        raise ValueError("Plugin scope is read-only. Plugins can only be managed through the marketplace.")
