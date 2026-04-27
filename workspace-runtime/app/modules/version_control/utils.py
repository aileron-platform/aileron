"""Git version control utility methods

Provides common Git operation utility functions and type definitions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, TYPE_CHECKING

from git import GitCommandError, InvalidGitRepositoryError, Repo

from .models import GitContext, GitContextListResponse

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)

# Git empty tree SHA constant
NULL_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# Performance protection constants
MAX_UNTRACKED_FILES = 50000  # Maximum number of untracked files
MAX_COMMIT_FILES = 10000     # Maximum files per commit


class VersionControlError(Exception):
    """Version control exception"""

    def __init__(self, message: str, status_code: int = 400, error_code: str = "VC_GENERIC") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass
class DiffEntry:
    """Diff entry"""
    path: str
    status: str
    change_type: str
    additions: int
    deletions: int
    patch: Optional[str]


class GitUtils:
    """Git utility methods collection

    Provides basic utility methods for Git operations.
    """

    def __init__(self, root_path: Path, cache: Optional["GitCache"] = None) -> None:
        """Initialize utility class

        Args:
            root_path: Workspace root directory
            cache: Cache layer (optional)
        """
        self._root_path = root_path
        self.cache = cache
        self._context_path_cache: dict[tuple[str, str], Path] = {}

    def workspace_path(self, workspace_id: str) -> Path:
        """Get workspace path

        Args:
            workspace_id: Workspace ID

        Returns:
            Workspace path

        Raises:
            VersionControlError: Workspace not found
        """
        # In container environment, directly use /workspace as working directory
        # In test environment, use workspace_id as subdirectory
        if self._root_path == Path("/workspace"):
            path = self._root_path
        else:
            path = self._root_path / workspace_id

        if not path.exists():
            raise VersionControlError(
                f"Workspace '{workspace_id}' not found",
                status_code=404,
                error_code="WORKSPACE_NOT_FOUND",
            )
        return path

    def list_contexts(self, workspace_id: str) -> GitContextListResponse:
        """List Git contexts for the primary checkout and managed worktrees."""
        workspace_root = self.workspace_path(workspace_id).resolve()
        repo = self.get_repo(workspace_id)
        contexts: list[GitContext] = []
        active_context_id = "primary"
        current_primary_branch, primary_detached = self.current_branch(repo)
        primary_head_sha = repo.head.commit.hexsha if self.has_head(repo) else None
        primary_head_ref = None if primary_detached else f"refs/heads/{current_primary_branch}"

        try:
            output = repo.git.worktree("list", "--porcelain")
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_WORKTREE_LIST_FAILED") from exc

        blocks = [block for block in output.split("\n\n") if block.strip()]
        for block in blocks:
            metadata: dict[str, str | bool] = {}
            for line in block.splitlines():
                if not line.strip():
                    continue
                key, _, value = line.partition(" ")
                if key in {"detached", "locked"}:
                    metadata[key] = True
                elif key == "prunable":
                    metadata[key] = bool(value.strip()) or True
                else:
                    metadata[key] = value.strip()

            raw_path = str(metadata.get("worktree", "")).strip()
            if not raw_path:
                continue

            repo_path = Path(raw_path).resolve()
            if repo_path == workspace_root:
                contexts.append(
                    GitContext(
                        id="primary",
                        kind="primary",
                        displayName=current_primary_branch or "primary",
                        repoPath=str(repo_path),
                        branch=current_primary_branch if current_primary_branch != "HEAD" else None,
                        headRef=primary_head_ref,
                        detached=primary_detached,
                        headSha=primary_head_sha,
                        locked=bool(metadata.get("locked", False)),
                        prunable=bool(metadata.get("prunable", False)),
                    )
                )
                continue

            managed_root = workspace_root / ".worktrees"
            if managed_root not in repo_path.parents:
                continue

            context_rel = repo_path.relative_to(managed_root).as_posix()
            branch_ref = str(metadata.get("branch", "")).strip() or None
            branch_name = branch_ref.split("refs/heads/", 1)[1] if branch_ref and branch_ref.startswith("refs/heads/") else branch_ref
            detached = bool(metadata.get("detached", False))
            contexts.append(
                GitContext(
                    id=f"worktree:{context_rel.replace('/', '--')}",
                    kind="worktree",
                    displayName=repo_path.name,
                    repoPath=str(repo_path),
                    branch=None if detached else branch_name,
                    headRef=None if detached else branch_ref,
                    detached=detached,
                    headSha=str(metadata.get("HEAD", "")).strip() or None,
                    locked=bool(metadata.get("locked", False)),
                    prunable=bool(metadata.get("prunable", False)),
                )
            )

        if not any(context.id == "primary" for context in contexts):
            contexts.insert(
                0,
                GitContext(
                    id="primary",
                    kind="primary",
                    displayName=current_primary_branch or "primary",
                    repoPath=str(workspace_root),
                    branch=current_primary_branch if current_primary_branch != "HEAD" else None,
                    headRef=primary_head_ref,
                    detached=primary_detached,
                    headSha=primary_head_sha,
                ),
            )

        contexts.sort(key=lambda item: (item.kind != "primary", item.displayName.lower()))
        return GitContextListResponse(activeContextId=active_context_id, contexts=contexts)

    def resolve_context_path(self, workspace_id: str, context_id: Optional[str] = None) -> Path:
        """Resolve a Git context id to a repository path."""
        if not context_id:
            return self.workspace_path(workspace_id).resolve()

        cache_key = (workspace_id, context_id)
        cached_path = self._context_path_cache.get(cache_key)
        if cached_path is not None:
            if cached_path.exists():
                return cached_path
            self._context_path_cache.pop(cache_key, None)

        context_map = {
            context.id: Path(context.repoPath).resolve()
            for context in self.list_contexts(workspace_id).contexts
        }
        resolved = context_map.get(context_id)
        if resolved is None:
            raise VersionControlError(
                f"Git context '{context_id}' not found",
                status_code=404,
                error_code="VC_CONTEXT_NOT_FOUND",
            )
        if not resolved.exists():
            raise VersionControlError(
                f"Git context '{context_id}' not found",
                status_code=404,
                error_code="VC_CONTEXT_NOT_FOUND",
            )
        self._context_path_cache[cache_key] = resolved
        return resolved

    def invalidate_context_path_cache(self, workspace_id: Optional[str] = None) -> None:
        """Invalidate cached Git context path resolutions."""
        if workspace_id is None:
            self._context_path_cache.clear()
            return
        for key in list(self._context_path_cache):
            if key[0] == workspace_id:
                self._context_path_cache.pop(key, None)

    def get_repo(self, workspace_id: str, context_id: Optional[str] = None) -> Repo:
        """Get Git Repository

        Args:
            workspace_id: Workspace ID

        Returns:
            Git Repository object

        Raises:
            VersionControlError: Not a Git repository
        """
        path = self.resolve_context_path(workspace_id, context_id)
        try:
            return Repo(path)
        except InvalidGitRepositoryError as exc:
            raise VersionControlError(
                "Workspace is not a git repository",
                status_code=400,
                error_code="VC_REPOSITORY_NOT_INITIALIZED",
            ) from exc

    @staticmethod
    def has_head(repo: Repo) -> bool:
        """Check if there is HEAD commit

        Args:
            repo: Git Repository

        Returns:
            Whether there is HEAD commit
        """
        try:
            _ = repo.head.commit
            return True
        except (ValueError, GitCommandError):
            return False

    @staticmethod
    def current_branch(repo: Repo) -> tuple[str, bool]:
        """Get current branch name

        Args:
            repo: Git Repository

        Returns:
            (Branch name, Whether it's detached HEAD)
        """
        detached = False
        branch_name = "HEAD"
        if not GitUtils.has_head(repo):
            # No commits yet, use default HEAD name
            try:
                branch_name = repo.active_branch.name
            except TypeError:
                branch_name = "HEAD"
            return branch_name, detached
        try:
            branch_name = repo.active_branch.name
        except (TypeError, GitCommandError):
            detached = True
            branch_name = repo.head.commit.hexsha[:7]
        return branch_name, detached

    @staticmethod
    def tracking_delta(repo: Repo) -> tuple[int, int]:
        """Calculate difference with tracking branch

        Args:
            repo: Git Repository

        Returns:
            (ahead count, behind count)
        """
        try:
            branch = repo.active_branch
        except (TypeError, GitCommandError):
            return 0, 0
        tracking = branch.tracking_branch()
        if not tracking:
            return 0, 0
        try:
            ahead = sum(1 for _ in repo.iter_commits(f"{tracking}..{branch}"))
            behind = sum(1 for _ in repo.iter_commits(f"{branch}..{tracking}"))
        except GitCommandError:
            return 0, 0
        return ahead, behind

    @staticmethod
    def last_fetch_time(repo: Repo) -> Optional[str]:
        """Get last fetch time

        Args:
            repo: Git Repository

        Returns:
            ISO format time string or None
        """
        fetch_head = Path(repo.git_dir) / "FETCH_HEAD"
        if not fetch_head.exists():
            return None
        ts = datetime.fromtimestamp(fetch_head.stat().st_mtime, tz=timezone.utc)
        return ts.isoformat().replace("+00:00", "Z")

    @staticmethod
    def should_ignore_file(file_path: str) -> bool:
        """Determine if file should be ignored

        Includes version control directories, dependency management directories, build artifacts, etc.

        Args:
            file_path: File path relative to workspace root directory

        Returns:
            True means should ignore, False means should display
        """
        # Version control directories
        if file_path.startswith('.git/') or file_path == '.git':
            return True
        if file_path.startswith('.svn/') or file_path == '.svn':
            return True
        if file_path.startswith('.hg/') or file_path == '.hg':
            return True

        # Python related
        if file_path.startswith('__pycache__/') or '/__pycache__/' in file_path:
            return True
        if file_path.startswith('.venv/') or file_path == '.venv':
            return True
        if file_path.startswith('venv/') or file_path == 'venv':
            return True
        if file_path.startswith('.pytest_cache/') or '/.pytest_cache/' in file_path:
            return True
        if file_path.startswith('.mypy_cache/') or '/.mypy_cache/' in file_path:
            return True
        if file_path.startswith('.ruff_cache/') or '/.ruff_cache/' in file_path:
            return True
        if file_path.endswith('.pyc') or file_path.endswith('.pyo'):
            return True
        if file_path.endswith('.egg-info') or '/.egg-info/' in file_path:
            return True

        # Node.js related
        if file_path.startswith('node_modules/') or '/node_modules/' in file_path:
            return True
        if file_path.startswith('.npm/') or file_path == '.npm':
            return True
        if file_path.startswith('.yarn/') or file_path == '.yarn':
            return True
        if file_path.startswith('.pnp/') or file_path == '.pnp':
            return True

        # Build artifacts
        if file_path.startswith('dist/') or file_path == 'dist':
            return True
        if file_path.startswith('build/') or file_path == 'build':
            return True
        if file_path.startswith('.next/') or file_path == '.next':
            return True
        if file_path.startswith('.nuxt/') or file_path == '.nuxt':
            return True
        if file_path.startswith('out/') or file_path == 'out':
            return True
        if file_path.startswith('target/') or file_path == 'target':  # Rust, Java
            return True

        # IDE and editors
        if file_path.startswith('.vscode/') or file_path == '.vscode':
            return True
        if file_path.startswith('.idea/') or file_path == '.idea':
            return True
        if file_path.startswith('.vs/') or file_path == '.vs':
            return True

        # Other language dependency directories
        if file_path.startswith('vendor/') or file_path == 'vendor':  # PHP, Go
            return True
        if file_path.startswith('.bundle/') or file_path == '.bundle':  # Ruby
            return True
        if file_path.startswith('Pods/') or file_path == 'Pods':  # iOS CocoaPods
            return True

        # Cache and temporary files
        if file_path.startswith('.cache/') or file_path == '.cache':
            return True
        if file_path.startswith('.tmp/') or file_path == '.tmp':
            return True
        if file_path.startswith('tmp/') or file_path == 'tmp':
            return True
        if file_path.startswith('.temp/') or file_path == '.temp':
            return True

        return False

    def diff_index(self, repo: Repo, staged: bool) -> list[DiffEntry]:
        """Get diff index

        Args:
            repo: Git Repository
            staged: Whether for staged changes

        Returns:
            DiffEntry list
        """
        if staged:
            diff = repo.index.diff("HEAD") if self.has_head(repo) else repo.index.diff(NULL_TREE)
        else:
            diff = repo.index.diff(None)
        stats = diff.stats.get("files", {}) if hasattr(diff, "stats") else {}
        entries: list[DiffEntry] = []
        for item in diff:
            path = item.b_path or item.a_path or ""
            if not path:
                continue
            stats_key_candidates = [path]
            if item.a_path:
                stats_key_candidates.append(item.a_path)
            if item.b_path:
                stats_key_candidates.append(item.b_path)
            if item.a_path and item.b_path and item.a_path != item.b_path:
                stats_key_candidates.append(f"{item.a_path} => {item.b_path}")
            stat = next((stats.get(key) for key in stats_key_candidates if key in stats), None)
            additions = int(stat.get("insertions", 0)) if stat else 0
            deletions = int(stat.get("deletions", 0)) if stat else 0

            entries.append(
                DiffEntry(
                    path=path,
                    status=item.change_type.upper(),
                    change_type=item.change_type,
                    additions=additions,
                    deletions=deletions,
                    patch=None,  # Don't preload patch, load on demand
                )
            )
        return entries

    @staticmethod
    def map_change_type(change_type: str) -> str:
        """Map change type

        Args:
            change_type: Git change type code

        Returns:
            Readable change type name
        """
        mapping = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
            "U": "unmerged",
        }
        return mapping.get(change_type.upper(), "modified")

    @staticmethod
    def normalize_paths(repo: Repo, paths: Iterable[str]) -> list[str]:
        """Normalize path list

        Args:
            repo: Git Repository
            paths: Original path list

        Returns:
            Normalized path list

        Raises:
            VersionControlError: No valid paths
        """
        normalized: list[str] = []
        for raw in paths:
            cleaned = raw.lstrip("/\\")
            if not cleaned:
                continue
            normalized.append(cleaned.replace("\\", "/"))
        if not normalized:
            raise VersionControlError("No valid paths provided", error_code="VC_INVALID_PATHS")
        return normalized

    @staticmethod
    def ensure_remote(repo: Repo, remote_name: str) -> None:
        """Ensure remote exists

        Args:
            repo: Git Repository
            remote_name: Remote name

        Raises:
            VersionControlError: Remote not found
        """
        if remote_name not in {remote.name for remote in repo.remotes}:
            raise VersionControlError(
                f"Remote '{remote_name}' not found",
                status_code=400,
                error_code="VC_REMOTE_NOT_FOUND",
            )


__all__ = [
    "DiffEntry",
    "GitUtils",
    "MAX_COMMIT_FILES",
    "MAX_UNTRACKED_FILES",
    "NULL_TREE",
    "VersionControlError",
]
