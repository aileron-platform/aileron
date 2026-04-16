"""Git 提交與歷史操作

提供 Git 提交建立和歷史記錄查詢功能。
"""

from __future__ import annotations

import logging
from datetime import timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from git import Actor, GitCommandError

from .cache import CacheKeys
from .models import (
    CommitAuthor,
    CommitChange,
    CommitDetailResponse,
    CommitFilesResponse,
    CommitListItem,
    CommitListResponse,
    CommitRequest,
    CommitResponse,
    CommitStats,
    CommitSummary,
)
from .utils import GitUtils, NULL_TREE, VersionControlError

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class CommitOperations:
    """Git 提交與歷史操作

    提供提交建立、提交列表、提交詳情等功能。
    """

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        """初始化

        Args:
            utils: Git 工具類實例
            cache: 快取層（可選）
        """
        self._utils = utils
        self.cache = cache

    def commit(self, workspace_id: str, payload: CommitRequest, context_id: Optional[str] = None) -> CommitResponse:
        """建立提交

        Args:
            workspace_id: 工作區 ID
            payload: 提交請求

        Returns:
            提交回應

        Raises:
            VersionControlError: 提交失敗
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        author = payload.author or CommitAuthor(name="Workspace Bot", email="workspace@example.com")
        actor = Actor(author.name, author.email)

        if payload.paths:
            normalized = self._utils.normalize_paths(repo, payload.paths)
            try:
                repo.index.add(normalized, write=True)
            except GitCommandError as exc:
                raise VersionControlError(str(exc), error_code="VC_STAGE_FAILED") from exc

        try:
            if payload.amend:
                repo.git.commit(
                    "--amend",
                    "-m",
                    payload.message,
                    "--author",
                    f"{author.name} <{author.email}>",
                )
                commit_obj = repo.head.commit
            else:
                commit_obj = repo.index.commit(
                    payload.message,
                    author=actor,
                    committer=actor,
                    skip_hooks=True,
                )
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_COMMIT_FAILED") from exc

        # 提交成功後，清除相關快取
        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.COMMITS)

        stats = commit_obj.stats.total
        summary = CommitSummary(
            id=commit_obj.hexsha,
            message=commit_obj.message.strip(),
            author=CommitAuthor(name=commit_obj.author.name, email=getattr(commit_obj.author, "email", "")),
            timestamp=commit_obj.committed_datetime.replace(tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            additions=stats.get("insertions", 0),
            deletions=stats.get("deletions", 0),
        )
        return CommitResponse(commit=summary)

    def list_commits(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 20,
        branch: Optional[str] = None,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> CommitListResponse:
        """列出提交歷史

        Args:
            workspace_id: 工作區 ID
            page: 頁碼
            page_size: 每頁大小
            branch: 分支名稱
            search: 搜尋關鍵字

        Returns:
            提交列表回應

        Raises:
            VersionControlError: 查詢失敗
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        if branch:
            target = branch
        else:
            target, _ = self._utils.current_branch(repo)
            # 如果當前分支是 HEAD 或無效，嘗試使用實際的分支
            if target == "HEAD" or target.startswith("HEAD"):
                try:
                    if repo.branches:
                        # 優先使用 main 或 master
                        for branch_name in ["main", "master"]:
                            if branch_name in [b.name for b in repo.branches]:
                                target = branch_name
                                break
                        else:
                            # 使用第一個可用分支
                            target = repo.branches[0].name
                except (AttributeError, IndexError, GitCommandError):
                    pass

        # 檢查是否有提交記錄
        if not self._utils.has_head(repo):
            return CommitListResponse(page=page, pageSize=page_size, total=0, items=[])

        # 效能優化: 如果有搜尋條件，需要載入更多 commits 來搜尋
        if search:
            try:
                commits = list(repo.iter_commits(target, max_count=1000))
            except GitCommandError as exc:
                raise VersionControlError(str(exc), error_code="VC_COMMITS_FAILED") from exc

            keyword = search.lower()
            filtered_commits = [
                c
                for c in commits
                if keyword in c.message.lower()
                or keyword in c.author.name.lower()
                or keyword in (getattr(c.author, "email", "") or "").lower()
            ]
            total = len(filtered_commits)
            start = max(page - 1, 0) * page_size
            end = start + page_size
            page_commits = filtered_commits[start:end]
        else:
            # 無搜尋: 使用 Git 原生分頁 - 大幅提升效能
            skip = max(page - 1, 0) * page_size
            try:
                page_commits = list(repo.iter_commits(target, max_count=page_size, skip=skip))

                # 優化：使用 git rev-list --count 快速取得總數
                try:
                    total = int(repo.git.rev_list("--count", target))
                except GitCommandError:
                    total_commits = list(repo.iter_commits(target, max_count=10000))
                    total = len(total_commits)
            except GitCommandError as exc:
                raise VersionControlError(str(exc), error_code="VC_COMMITS_FAILED") from exc

        try:
            branch_name = branch or repo.active_branch.name
        except (TypeError, GitCommandError):
            branch_name = branch or "HEAD"

        items = []
        for commit in page_commits:
            items.append(
                CommitListItem(
                    id=commit.hexsha,
                    message=commit.message.strip(),
                    author=commit.author.name,
                    email=getattr(commit.author, "email", None),
                    timestamp=int(commit.committed_datetime.replace(tzinfo=timezone.utc).timestamp() * 1000),
                    branch=branch_name,
                    additions=0,  # 不在列表中計算，提升效能
                    deletions=0,
                    files=0,
                )
            )
        return CommitListResponse(page=page, pageSize=page_size, total=total, items=items)

    def get_commit(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> CommitDetailResponse:
        """取得提交詳情

        Args:
            workspace_id: 工作區 ID
            commit_id: 提交 ID

        Returns:
            提交詳情回應

        Raises:
            VersionControlError: 提交不存在
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        try:
            commit = repo.commit(commit_id)
        except (ValueError, GitCommandError) as exc:
            raise VersionControlError("Commit not found", status_code=404, error_code="VC_COMMIT_NOT_FOUND") from exc

        # 處理 parent commit
        diff_parent = NULL_TREE
        if commit.parents:
            try:
                parent_commit = commit.parents[0]
                _ = parent_commit.hexsha
                diff_parent = parent_commit
            except (ValueError, GitCommandError):
                diff_parent = NULL_TREE

        # 獲取統計資訊
        stats = {}
        per_file_stats = {}
        try:
            commit_stats = commit.stats
            stats = commit_stats.total
            per_file_stats = commit_stats.files
        except GitCommandError:
            stats = {"insertions": 0, "deletions": 0, "files": 0, "lines": 0}
            per_file_stats = {}

        # 獲取 diff
        try:
            diffs = commit.diff(diff_parent, create_patch=True)
        except GitCommandError as exc:
            if diff_parent != NULL_TREE:
                try:
                    diffs = commit.diff(NULL_TREE, create_patch=True)
                except GitCommandError as inner_exc:
                    raise VersionControlError(
                        "Failed to get commit diff",
                        status_code=500,
                        error_code="VC_DIFF_FAILED"
                    ) from inner_exc
            else:
                raise VersionControlError(
                    f"Failed to get commit diff: {exc}",
                    status_code=500,
                    error_code="VC_DIFF_FAILED"
                ) from exc

        changes: list[CommitChange] = []
        total_additions = 0
        total_deletions = 0
        for diff in diffs:
            path = (diff.b_path or diff.a_path or "").replace("\\", "/")
            stats_key_candidates = [path]
            if diff.a_path:
                stats_key_candidates.append(diff.a_path)
            if diff.b_path:
                stats_key_candidates.append(diff.b_path)
            if diff.a_path and diff.b_path and diff.a_path != diff.b_path:
                stats_key_candidates.append(f"{diff.a_path} => {diff.b_path}")
            stat = next((per_file_stats.get(key) for key in stats_key_candidates if key in per_file_stats), {})
            additions = stat.get("insertions", 0) if stat else 0
            deletions = stat.get("deletions", 0) if stat else 0
            total_additions += additions
            total_deletions += deletions
            changes.append(
                CommitChange(
                    name=Path(path).name if path else "",
                    path=path,
                    status=(diff.change_type or "M").upper(),
                    additions=additions,
                    deletions=deletions,
                )
            )

        # 如果 stats 為空，使用手動計算的值
        if not stats or stats.get("insertions", 0) == 0:
            stats = {
                "insertions": total_additions,
                "deletions": total_deletions,
                "files": len(changes),
                "lines": total_additions + total_deletions,
            }

        detail = CommitDetailResponse(
            id=commit.hexsha,
            message=commit.message.strip(),
            author=CommitAuthor(name=commit.author.name, email=getattr(commit.author, "email", "")),
            timestamp=commit.committed_datetime.replace(tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            branch=repo.active_branch.name if not repo.head.is_detached else "HEAD",
            stats=CommitStats(
                additions=stats.get("insertions", 0),
                deletions=stats.get("deletions", 0),
                files=stats.get("files", 0),
            ),
            changes=changes,
        )
        return detail

    def get_commit_files(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> CommitFilesResponse:
        """取得提交的檔案列表

        Args:
            workspace_id: 工作區 ID
            commit_id: 提交 ID

        Returns:
            提交檔案回應

        Raises:
            VersionControlError: 提交不存在
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        try:
            commit = repo.commit(commit_id)
        except (ValueError, GitCommandError) as exc:
            raise VersionControlError("Commit not found", status_code=404, error_code="VC_COMMIT_NOT_FOUND") from exc

        # 效能優化: 使用 git diff-tree 批量取得檔案資訊和統計
        try:
            numstat_output = repo.git.diff_tree('-r', '--numstat', '--root', commit.hexsha)
            file_stats = {}
            for line in numstat_output.strip().split('\n'):
                if not line or line.startswith(':'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    additions = parts[0]
                    deletions = parts[1]
                    filename = parts[2]
                    add_count = 0 if additions == '-' else int(additions)
                    del_count = 0 if deletions == '-' else int(deletions)
                    file_stats[filename] = {
                        'insertions': add_count,
                        'deletions': del_count
                    }
        except GitCommandError:
            file_stats = {}

        # 使用 git show 命令獲取 patch
        try:
            show_output = repo.git.show(commit.hexsha, format="", no_color=True, no_ext_diff=True)
        except GitCommandError as exc:
            raise VersionControlError(
                f"Failed to get commit diff: {exc}",
                status_code=500,
                error_code="VC_DIFF_FAILED"
            ) from exc

        # 解析 git show 輸出，按檔案分組
        file_patches = {}
        current_file = None
        current_patch_lines = []

        for line in show_output.split('\n'):
            if line.startswith('diff --git'):
                if current_file and current_patch_lines:
                    file_patches[current_file] = '\n'.join(current_patch_lines)

                parts = line.split(' ')
                if len(parts) >= 4:
                    path_a = parts[2][2:] if parts[2].startswith('a/') else parts[2]
                    path_b = parts[3][2:] if parts[3].startswith('b/') else parts[3]
                    current_file = path_b if path_b != '/dev/null' else path_a
                    current_patch_lines = [line]
            elif current_file:
                current_patch_lines.append(line)

        if current_file and current_patch_lines:
            file_patches[current_file] = '\n'.join(current_patch_lines)

        # 構建檔案列表
        files: list[CommitChange] = []
        for path, patch_text in file_patches.items():
            stat = file_stats.get(path, {})

            # 從 patch 中判斷變更類型
            status = "M"
            if "new file mode" in patch_text:
                status = "A"
            elif "deleted file mode" in patch_text:
                status = "D"
            elif "rename from" in patch_text:
                status = "R"

            files.append(
                CommitChange(
                    name=path.split("/")[-1] if path else "",
                    path=path,
                    status=status,
                    additions=stat.get("insertions", 0),
                    deletions=stat.get("deletions", 0),
                    patch=patch_text or None,
                )
            )

        return CommitFilesResponse(commitId=commit.hexsha, files=files)


__all__ = ["CommitOperations"]
