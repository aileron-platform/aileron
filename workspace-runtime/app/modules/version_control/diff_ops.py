"""Git diff and content operations

Provides Git diff query and blob content reading functionality.
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
    """Git diff and content operations

    Provides diff query, blob content reading and other functionality.
    """

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        """Initialize

        Args:
            utils: Git utility class instance
            cache: Cache layer (optional)
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
        context_id: Optional[str] = None,
    ) -> DiffResponse:
        """Get file diff content

        Args:
            workspace_id: Workspace ID
            path: File path
            base: Comparison base (default is HEAD)
            head: Comparison target (None/WORKTREE=working directory, INDEX=index, other=commit ID)
            context: Context line count
            include_metadata: Whether to include file metadata

        Returns:
            DiffResponse: Response containing diff content
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        normalized = path.lstrip("/\\")

        if head in (None, "WORKTREE"):
            # Unstaged changes: compare index with working directory
            base_ref, head_label = "INDEX", "WORKTREE"
            diff_text = self._get_worktree_diff(repo, normalized, context)
        elif head == "INDEX":
            # Staged changes: compare HEAD with index
            base_ref = base or "HEAD"
            head_label = "INDEX"
            diff_text = self._get_staged_diff(repo, normalized, base_ref, context)
        else:
            # Inter-commit diff: compare two commits
            base_ref = base or "HEAD"
            head_label = head
            diff_text = self._get_commit_diff(repo, normalized, base_ref, head, context)

        # Get file metadata
        metadata = self._get_file_metadata(repo, normalized, base_ref) if include_metadata else None

        return DiffResponse(
            path=normalized,
            base=base_ref,
            head=head_label,
            context=context,
            patch=diff_text,
            metadata=metadata,
        )

    def blob(
        self,
        workspace_id: str,
        path: str,
        revision: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> BlobResponse:
        """Get file content

        Args:
            workspace_id: Workspace ID
            path: File path
            revision: Version (default is HEAD)

        Returns:
            BlobResponse: Response containing file content

        Raises:
            VersionControlError: File does not exist
        """
        repo = self._utils.get_repo(workspace_id, context_id)
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
        """Get diff between working directory and index"""
        try:
            # Use -c core.quotepath=false to support Chinese filenames
            diff_text = repo.git.execute(
                ["git", "-c", "core.quotepath=false", "diff", f"-U{context}", "--", path]
            )

            # Check if binary file
            if "Binary files" in diff_text or not diff_text:
                file_path = Path(repo.working_tree_dir) / path
                if file_path.exists() and self._is_binary_file(file_path):
                    return f"Binary file: {path}\n(Binary files cannot be displayed)"

            # Handle untracked new files
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
        """Get diff of staged changes"""
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
        """Get diff between commits"""
        try:
            return repo.git.diff(base_ref, head_ref, f"-U{context}", "--", path)
        except GitCommandError:
            return ""

    def _is_binary_file(self, file_path: Path) -> bool:
        """Detect if file is binary"""
        try:
            # Check file size (consider as binary if over 10MB)
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return True

            # Read first 8192 bytes for detection
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)

            # Check if contains null byte (characteristic of binary files)
            if b'\x00' in chunk:
                return True

            # Try to decode as UTF-8
            try:
                chunk.decode('utf-8', errors='ignore')
                return False
            except UnicodeDecodeError:
                return True

        except (OSError, IOError):
            return True

    def _create_new_file_diff(self, repo: Repo, path: str) -> str:
        """Create diff format content for new files"""
        file_path = Path(repo.working_tree_dir) / path
        if not file_path.exists() or not file_path.is_file():
            return ""

        # Check if binary file
        if self._is_binary_file(file_path):
            file_size = file_path.stat().st_size
            size_str = self._format_file_size(file_size)
            return f"Binary file: {path}\nSize: {size_str}\n(Binary files cannot be displayed)"

        # Check file size (text files over 1MB also won't show full content)
        file_size = file_path.stat().st_size
        if file_size > 1 * 1024 * 1024:  # 1MB
            size_str = self._format_file_size(file_size)
            return f"Large text file: {path}\nSize: {size_str}\n(File too large to display, please use external editor)"

        try:
            with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
                content = f.read()

            lines = content.splitlines()

            # Limit to maximum 1000 lines
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
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _get_file_metadata(self, repo: Repo, path: str, base_ref: str) -> Optional[dict]:
        """Get file metadata"""
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
