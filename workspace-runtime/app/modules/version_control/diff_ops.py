"""Git Diff 與內容操作

提供 Git diff 查詢和 blob 內容讀取功能。
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from git import GitCommandError, Repo

from .models import BlobResponse, DiffResponse
from .utils import GitUtils, NULL_TREE, VersionControlError

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class DiffOperations:
    """Git Diff 與內容操作

    提供 diff 查詢、blob 內容讀取等功能。
    """

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        """初始化

        Args:
            utils: Git 工具類實例
            cache: 快取層（可選）
        """
        self._utils = utils
        self.cache = cache

    def diff(
        self,
        workspace_id: str,
        path: str,
        base: Optional[str] = None,
        head: Optional[str] = None,
        context: int = 3,
        include_metadata: bool = False,
    ) -> DiffResponse:
        """獲取檔案的差異內容

        Args:
            workspace_id: 工作區 ID
            path: 檔案路徑
            base: 比較基準（預設為 HEAD）
            head: 比較目標（None/WORKTREE=工作目錄, INDEX=索引, 其他=提交ID）
            context: 上下文行數
            include_metadata: 是否包含檔案元資料

        Returns:
            DiffResponse: 包含差異內容的回應
        """
        repo = self._utils.get_repo(workspace_id)
        normalized = path.lstrip("/\\")

        if head in (None, "WORKTREE"):
            # 未暫存的變更：比較索引與工作目錄
            base_ref, head_label = "INDEX", "WORKTREE"
            diff_text = self._get_worktree_diff(repo, normalized, context)
        elif head == "INDEX":
            # 已暫存的變更：比較 HEAD 與索引
            base_ref = base or "HEAD"
            head_label = "INDEX"
            diff_text = self._get_staged_diff(repo, normalized, base_ref, context)
        else:
            # 提交間差異：比較兩個提交
            base_ref = base or "HEAD"
            head_label = head
            diff_text = self._get_commit_diff(repo, normalized, base_ref, head, context)

        # 獲取檔案元資料
        metadata = self._get_file_metadata(repo, normalized, base_ref) if include_metadata else None

        return DiffResponse(
            path=normalized,
            base=base_ref,
            head=head_label,
            context=context,
            patch=diff_text,
            metadata=metadata,
        )

    def blob(self, workspace_id: str, path: str, revision: Optional[str] = None) -> BlobResponse:
        """獲取檔案內容

        Args:
            workspace_id: 工作區 ID
            path: 檔案路徑
            revision: 版本（預設為 HEAD）

        Returns:
            BlobResponse: 包含檔案內容的回應

        Raises:
            VersionControlError: 檔案不存在
        """
        repo = self._utils.get_repo(workspace_id)
        normalized = path.lstrip("/\\")
        rev = revision or "HEAD"

        try:
            data = repo.git.show(f"{rev}:{normalized}")
            raw = data.encode("utf-8")
        except GitCommandError as exc:
            raise VersionControlError("Blob not found", status_code=404, error_code="VC_BLOB_NOT_FOUND") from exc

        encoded = base64.b64encode(raw).decode("ascii")
        return BlobResponse(path=normalized, revision=rev, encoding="utf-8", content=encoded, isBase64=True)

    def _get_worktree_diff(self, repo: Repo, path: str, context: int) -> str:
        """獲取工作目錄與索引的差異"""
        try:
            # 使用 -c core.quotepath=false 支援中文檔名
            diff_text = repo.git.execute(
                ["git", "-c", "core.quotepath=false", "diff", f"-U{context}", "--", path]
            )

            # 檢查是否為二進位檔案
            if "Binary files" in diff_text or not diff_text:
                file_path = Path(repo.working_tree_dir) / path
                if file_path.exists() and self._is_binary_file(file_path):
                    return f"Binary file: {path}\n(Binary files cannot be displayed)"

            # 處理未追蹤的新檔案
            if not diff_text:
                try:
                    result = repo.git.execute(
                        ["git", "-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard", "--", path]
                    )
                    if result.strip():
                        diff_text = self._create_new_file_diff(repo, path)
                except GitCommandError:
                    pass

            return diff_text
        except GitCommandError:
            return ""

    def _get_staged_diff(self, repo: Repo, path: str, base_ref: str, context: int) -> str:
        """獲取已暫存變更的差異"""
        try:
            if self._utils.has_head(repo):
                diff_text = repo.git.diff(base_ref, "--cached", f"-U{context}", "--", path)
            else:
                diff_text = repo.git.diff(NULL_TREE, "--cached", f"-U{context}", "--", path)

            if "Binary files" in diff_text:
                return f"Binary file: {path}\n(Binary files cannot be displayed)"

            return diff_text
        except GitCommandError:
            return ""

    def _get_commit_diff(self, repo: Repo, path: str, base_ref: str, head_ref: str, context: int) -> str:
        """獲取提交間的差異"""
        try:
            return repo.git.diff(base_ref, head_ref, f"-U{context}", "--", path)
        except GitCommandError:
            return ""

    def _is_binary_file(self, file_path: Path) -> bool:
        """檢測檔案是否為二進位檔案"""
        try:
            # 檢查檔案大小（超過 10MB 視為二進位）
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return True

            # 讀取前 8192 bytes 檢測
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)

            # 檢查是否包含 null byte（二進位檔案的特徵）
            if b'\x00' in chunk:
                return True

            # 嘗試解碼為 UTF-8
            try:
                chunk.decode('utf-8', errors='ignore')
                return False
            except UnicodeDecodeError:
                return True

        except (OSError, IOError):
            return True

    def _create_new_file_diff(self, repo: Repo, path: str) -> str:
        """為新建檔案創建 diff 格式內容"""
        file_path = Path(repo.working_tree_dir) / path
        if not file_path.exists() or not file_path.is_file():
            return ""

        # 檢查是否為二進位檔案
        if self._is_binary_file(file_path):
            file_size = file_path.stat().st_size
            size_str = self._format_file_size(file_size)
            return f"Binary file: {path}\nSize: {size_str}\n(Binary files cannot be displayed)"

        # 檢查檔案大小（超過 1MB 的文字檔案也不顯示完整內容）
        file_size = file_path.stat().st_size
        if file_size > 1 * 1024 * 1024:  # 1MB
            size_str = self._format_file_size(file_size)
            return f"Large text file: {path}\nSize: {size_str}\n(File too large to display, please use external editor)"

        try:
            with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
                content = f.read()

            lines = content.splitlines()

            # 限制最多顯示 1000 行
            if len(lines) > 1000:
                diff_lines = [
                    "--- /dev/null",
                    f"+++ b/{path}",
                    f"@@ -0,0 +1,{len(lines)} @@",
                    "+... (showing first 1000 lines of " + str(len(lines)) + " total lines)"
                ]
                diff_lines.extend(f"+{line}" for line in lines[:1000])
                diff_lines.append("+... (" + str(len(lines) - 1000) + " more lines omitted)")
            else:
                diff_lines = [
                    "--- /dev/null",
                    f"+++ b/{path}",
                    f"@@ -0,0 +1,{len(lines)} @@"
                ]
                diff_lines.extend(f"+{line}" for line in lines)

            return '\n'.join(diff_lines)

        except (OSError, UnicodeDecodeError):
            return f"Binary file: {path}\n(Unable to read file content)"

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """格式化檔案大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _get_file_metadata(self, repo: Repo, path: str, base_ref: str) -> Optional[dict]:
        """獲取檔案元資料"""
        if base_ref in ("INDEX", "WORKTREE"):
            return None

        try:
            ls_output = repo.git.ls_tree(base_ref, path)
            if ls_output:
                parts = ls_output.split()
                return {"oldMode": parts[0], "newMode": parts[0]}
        except GitCommandError:
            pass
        return None


__all__ = ["DiffOperations"]
