"""Knowledge base scoped Git version control service."""

from __future__ import annotations

import difflib
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from git import GitCommandError, InvalidGitRepositoryError, Repo
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.models.template_git import (
    GitRepositoryStatus,
    TemplateBlobResponse,
    TemplateBranchCommitInfo,
    TemplateChangesResponse,
    TemplateCheckoutRequest,
    TemplateCheckoutResponse,
    TemplateCommitFilesResponse,
    TemplateCommitListResponse,
    TemplateCommitResponse,
    TemplateCommitSummary,
    TemplateDiffResponse,
    TemplateDiscardRequest,
    TemplateDiscardResponse,
    TemplateFileChange,
    TemplateRemoteRequest,
    TemplateRemoteResponse,
    TemplateStageRequest,
    TemplateStageResponse,
    TemplateUnstageRequest,
    TemplateUnstageResponse,
    TemplateVersionControlBranch,
    TemplateVersionControlBranchListResponse,
    TemplateVersionControlStatus,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService

logger = logging.getLogger(__name__)

KB_VERSION_CONTROL_DISABLED = "KB_VERSION_CONTROL_DISABLED"


class KnowledgeBaseGitService:
    """Manage optional Git operations for a single knowledge base repository."""

    DEFAULT_LFS_PATTERNS = (
        "raw/**/*.pdf",
        "raw/**/*.zip",
        "raw/**/*.png",
        "raw/**/*.jpg",
        "raw/**/*.jpeg",
        "raw/**/*.gif",
        "raw/**/*.webp",
        "raw/**/*.pptx",
        "raw/**/*.docx",
        "raw/**/*.xlsx",
    )

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)

    def enable(
        self,
        *,
        user_id: str,
        kb_id: str,
        default_branch: str = "main",
        initial_message: str = "Initialize knowledge base",
    ) -> GitRepositoryStatus:
        """Enable Git version control for a KB."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="manager")
        self._ensure_wiki(kb)
        root = self._kb_root(kb.id)
        repo = self._repo_or_init(root, default_branch=default_branch)
        self._ensure_default_ignore(root)
        if not repo.head.is_valid():
            repo.git.add("--all")
            if self._has_staged_changes(repo):
                commit = repo.index.commit(initial_message)
                kb.git_last_commit_sha = commit.hexsha
        kb.version_control_enabled = True
        kb.git_default_branch = default_branch
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)
        return self.repository_status(user_id=user_id, kb_id=kb_id)

    def enable_lfs(self, *, user_id: str, kb_id: str, patterns: Optional[list[str]] = None) -> None:
        """Enable Git LFS tracking for common raw source patterns."""
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="manager")
        repo = self._require_repo(kb)
        root = self._kb_root(kb.id)
        subprocess.run(["git", "lfs", "install", "--local"], cwd=root, check=False, capture_output=True, text=True)
        lines = [
            f"{pattern} filter=lfs diff=lfs merge=lfs -text"
            for pattern in (patterns or list(self.DEFAULT_LFS_PATTERNS))
        ]
        attributes = root / ".gitattributes"
        existing = attributes.read_text(encoding="utf-8").splitlines() if attributes.exists() else []
        merged = list(dict.fromkeys(existing + lines))
        attributes.write_text("\n".join(merged) + "\n", encoding="utf-8")
        repo.index.add([".gitattributes"])
        kb.git_lfs_enabled = True
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)

    def repository_status(self, *, user_id: str, kb_id: str) -> GitRepositoryStatus:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        root = self._kb_root(kb.id)
        repo = self._get_repo(root)
        if repo is None:
            return GitRepositoryStatus(
                is_git_repo=False,
                current_branch=None,
                remote_url=None,
                has_origin=False,
                has_local_content=root.exists() and any(root.iterdir()),
                can_clone_safely=False,
                can_init_safely=True,
                clone_blocked_reason=None,
            )
        remote_url = self._origin_url(repo)
        return GitRepositoryStatus(
            is_git_repo=True,
            current_branch=self._repository_branch(repo),
            remote_url=remote_url,
            has_origin=bool(remote_url),
            has_local_content=True,
            can_clone_safely=False,
            can_init_safely=False,
            clone_blocked_reason="GIT_REPOSITORY_ALREADY_INITIALIZED",
        )

    def get_version_control_status(self, *, user_id: str, kb_id: str) -> TemplateVersionControlStatus:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer"))
        branch, detached = self._current_branch_name(repo)
        staged = self._staged_file_changes(repo)
        unstaged = repo.index.diff(None)
        ahead, behind = self._tracking_delta_for_branch(repo, branch) if not detached else (0, 0)
        return TemplateVersionControlStatus(
            branch=branch,
            ahead=ahead,
            behind=behind,
            detached=detached,
            hasConflicts=bool(self._conflict_files(repo)),
            stagedCount=len(staged),
            unstagedCount=len(unstaged),
            untrackedCount=len(repo.untracked_files),
        )

    def get_file_changes(self, *, user_id: str, kb_id: str, page: int = 1, page_size: int = 100) -> TemplateChangesResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer"))
        staged = self._staged_file_changes(repo)
        unstaged = []
        for diff_item in repo.index.diff(None):
            path = diff_item.b_path or diff_item.a_path or ""
            if path:
                unstaged.append(self._file_change(repo, path, diff_item.change_type or "M"))
        start = (page - 1) * page_size
        end = start + page_size
        untracked = [
            TemplateFileChange(name=Path(path).name, path=path, status="??", type="untracked")
            for path in repo.untracked_files[start:end]
        ]
        return TemplateChangesResponse(
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            untrackedTotal=len(repo.untracked_files),
            untrackedPage=page,
            untrackedPageSize=page_size,
            untrackedHasMore=end < len(repo.untracked_files),
        )

    def stage(self, *, user_id: str, kb_id: str, payload: TemplateStageRequest) -> TemplateStageResponse:
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        repo = self._require_repo(kb)
        paths = self._safe_repo_paths(kb.id, payload.paths)
        repo.index.add(paths)
        return TemplateStageResponse(staged=paths, unstaged=[item.path for item in self.get_file_changes(user_id=user_id, kb_id=kb_id).unstaged])

    def unstage(self, *, user_id: str, kb_id: str, payload: TemplateUnstageRequest) -> TemplateUnstageResponse:
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        repo = self._require_repo(kb)
        paths = self._safe_repo_paths(kb.id, payload.paths)
        repo.git.reset("HEAD", "--", *paths)
        return TemplateUnstageResponse(unstaged=paths, remainingStaged=len(self.get_file_changes(user_id=user_id, kb_id=kb_id).staged))

    def discard(self, *, user_id: str, kb_id: str, payload: TemplateDiscardRequest) -> TemplateDiscardResponse:
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        repo = self._require_repo(kb)
        paths = self._safe_repo_paths(kb.id, payload.paths)
        warnings = []
        root = self._kb_root(kb.id)
        for path in paths:
            target = root / path
            if path in repo.untracked_files:
                if target.is_file():
                    target.unlink()
                else:
                    warnings.append(path)
                continue
            repo.git.checkout("--", path)
        return TemplateDiscardResponse(discarded=paths, warnings=warnings)

    def commit(self, *, user_id: str, kb_id: str, message: str, paths: Optional[list[str]] = None) -> TemplateCommitResponse:
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        repo = self._require_repo(kb)
        if paths:
            repo.index.add(self._safe_repo_paths(kb.id, paths))
        return self._commit_staged(kb, repo, message=message)

    def commit_all(self, *, user_id: str, kb_id: str, message: str) -> TemplateCommitResponse:
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        repo = self._require_repo(kb)
        repo.git.add("--all")
        return self._commit_staged(kb, repo, message=message)

    def list_commits(self, *, user_id: str, kb_id: str, page: int = 1, page_size: int = 20) -> TemplateCommitListResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer"))
        if not repo.head.is_valid():
            return TemplateCommitListResponse(page=page, pageSize=page_size, total=0, items=[])
        commits = list(repo.iter_commits("HEAD"))
        start = (page - 1) * page_size
        end = start + page_size
        return TemplateCommitListResponse(
            page=page,
            pageSize=page_size,
            total=len(commits),
            items=[self._commit_summary(repo, commit) for commit in commits[start:end]],
        )

    def get_commit_files(self, *, user_id: str, kb_id: str, commit_id: str) -> TemplateCommitFilesResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer"))
        commit = repo.commit(commit_id)
        parent = f"{commit.hexsha}^" if commit.parents else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        files = []
        for line in repo.git.diff("--numstat", parent, commit.hexsha).splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            path = parts[2]
            patch = repo.git.diff(parent, commit.hexsha, "--", path)
            files.append(
                TemplateFileChange(
                    name=Path(path).name,
                    path=path,
                    status="M",
                    type="modified",
                    additions=int(parts[0]) if parts[0].isdigit() else 0,
                    deletions=int(parts[1]) if parts[1].isdigit() else 0,
                    diff=patch,
                    patch=patch,
                )
            )
        return TemplateCommitFilesResponse(commitId=commit_id, files=files)

    def diff(self, *, user_id: str, kb_id: str, path: str, head: str = "WORKTREE") -> TemplateDiffResponse:
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        repo = self._require_repo(kb)
        safe_path = self._safe_repo_path(kb.id, path)
        if head != "INDEX" and safe_path in repo.untracked_files:
            patch = self._untracked_file_diff(kb.id, safe_path)
            return TemplateDiffResponse(path=safe_path, patch=patch, diff=patch, binary=False)
        args = ["--cached"] if head == "INDEX" else []
        args.extend(["--", safe_path])
        patch = repo.git.diff(*args)
        return TemplateDiffResponse(path=safe_path, patch=patch, diff=patch, binary="Binary files" in patch)

    def blob(self, *, user_id: str, kb_id: str, path: str, revision: Optional[str] = None) -> TemplateBlobResponse:
        kb = self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        repo = self._require_repo(kb)
        safe_path = self._safe_repo_path(kb.id, path)
        content = repo.git.show(f"{revision}:{safe_path}") if revision else (self._kb_root(kb.id) / safe_path).read_text(encoding="utf-8")
        return TemplateBlobResponse(path=safe_path, revision=revision, content=content)

    def list_branches(self, *, user_id: str, kb_id: str) -> TemplateVersionControlBranchListResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer"))
        current, detached = self._current_branch_name(repo)
        branches = []
        for head in repo.heads:
            ahead, behind = self._tracking_delta_for_branch(repo, head.name)
            branches.append(
                TemplateVersionControlBranch(
                    name=head.name,
                    displayName=head.name,
                    isActive=(not detached and head.name == current),
                    isRemote=False,
                    ahead=ahead,
                    behind=behind,
                    lastCommit=self._branch_commit_info(head),
                )
            )
        for remote in repo.remotes:
            for ref in remote.refs:
                if ref.remote_head == "HEAD" or any(branch.name == ref.remote_head for branch in branches):
                    continue
                branches.append(
                    TemplateVersionControlBranch(
                        name=ref.remote_head,
                        displayName=ref.remote_head,
                        isActive=False,
                        isRemote=True,
                        lastCommit=self._branch_commit_info(ref),
                    )
                )
        return TemplateVersionControlBranchListResponse(branches=branches)

    def checkout_branch(self, *, user_id: str, kb_id: str, branch_name: str, payload: TemplateCheckoutRequest) -> TemplateCheckoutResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor"))
        stashed = None
        if payload.stashChanges and self.get_version_control_status(user_id=user_id, kb_id=kb_id).unstagedCount:
            stashed = repo.git.stash("push", "-u", "-m", f"kb-checkout-{branch_name}")
        created = False
        if payload.create:
            repo.git.checkout("-b", branch_name, payload.startPoint or "HEAD")
            created = True
        else:
            repo.git.checkout(branch_name)
        return TemplateCheckoutResponse(branch=branch_name, created=created, stashedChanges=stashed)

    def set_remote_url(self, *, user_id: str, kb_id: str, url: str) -> None:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="manager"))
        if "origin" in repo.remotes:
            repo.remotes.origin.set_url(url.strip())
        else:
            repo.create_remote("origin", url.strip())

    def fetch(self, *, user_id: str, kb_id: str, payload: TemplateRemoteRequest) -> TemplateRemoteResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor"))
        repo.remotes[payload.remote].fetch()
        return TemplateRemoteResponse(remote=payload.remote, branch=payload.branch, message="GIT_FETCH_SUCCESS")

    def pull(self, *, user_id: str, kb_id: str, payload: TemplateRemoteRequest) -> TemplateRemoteResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor"))
        branch, _ = self._current_branch_name(repo)
        target = payload.branch or branch
        args = [payload.remote, target]
        if payload.rebase:
            args.insert(0, "--rebase")
        if payload.autostash:
            args.insert(0, "--autostash")
        repo.git.pull(*args)
        return TemplateRemoteResponse(remote=payload.remote, branch=target, message="GIT_PULL_SUCCESS")

    def push(self, *, user_id: str, kb_id: str, payload: TemplateRemoteRequest) -> TemplateRemoteResponse:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor"))
        branch, _ = self._current_branch_name(repo)
        target = payload.branch or branch
        args = [target]
        if payload.force:
            args.insert(0, "--force")
        repo.remotes[payload.remote].push(*args)
        return TemplateRemoteResponse(remote=payload.remote, branch=target, message="GIT_PUSH_SUCCESS")

    def revert_commit(self, *, user_id: str, kb_id: str, commit_id: str) -> None:
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor"))
        repo.git.revert(commit_id, "--no-edit")

    def rollback(self, *, user_id: str, kb_id: str, revision: str, confirm: str) -> None:
        if confirm != "RESET_KB_GIT":
            raise ValueError("KB_GIT_ROLLBACK_CONFIRMATION_REQUIRED")
        repo = self._require_repo(self._require_enabled_kb(user_id=user_id, kb_id=kb_id, minimum_role="manager"))
        repo.git.reset("--hard", revision)

    def _require_enabled_kb(self, *, user_id: str, kb_id: str, minimum_role: str) -> db_models.KnowledgeBase:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role=minimum_role)
        if not kb.version_control_enabled:
            raise ValueError(KB_VERSION_CONTROL_DISABLED)
        return kb

    def _ensure_wiki(self, kb: db_models.KnowledgeBase) -> None:
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)

    def _repo_or_init(self, root: Path, *, default_branch: str) -> Repo:
        repo = self._get_repo(root)
        if repo is not None:
            return repo
        repo = Repo.init(str(root), initial_branch=default_branch)
        with repo.config_writer() as config:
            config.set_value("user", "name", "Aileron KB")
            config.set_value("user", "email", "kb@aileron.local")
        return repo

    def _get_repo(self, root: Path) -> Optional[Repo]:
        try:
            return Repo(str(root))
        except InvalidGitRepositoryError:
            return None

    def _require_repo(self, kb: db_models.KnowledgeBase) -> Repo:
        repo = self._get_repo(self._kb_root(kb.id))
        if repo is None:
            raise ValueError("GIT_REPO_NOT_FOUND")
        return repo

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _safe_repo_path(self, kb_id: str, path: str) -> str:
        normalized = path.strip().replace("\\", "/").lstrip("/")
        if not normalized or normalized == "." or ".." in Path(normalized).parts:
            raise ValueError("GIT_PATH_OUTSIDE_REPOSITORY")
        root = self._kb_root(kb_id).resolve()
        target = (root / normalized).resolve()
        if root != target and root not in target.parents:
            raise ValueError("GIT_PATH_OUTSIDE_REPOSITORY")
        return normalized

    def _safe_repo_paths(self, kb_id: str, paths: list[str]) -> list[str]:
        return [self._safe_repo_path(kb_id, path) for path in paths]

    def _ensure_default_ignore(self, root: Path) -> None:
        ignore = root / ".gitignore"
        line = ".aileron-kb/\n"
        if not ignore.exists():
            ignore.write_text(line, encoding="utf-8")
            return
        content = ignore.read_text(encoding="utf-8")
        if ".aileron-kb/" not in content.splitlines():
            ignore.write_text(content.rstrip() + "\n" + line, encoding="utf-8")

    @staticmethod
    def _origin_url(repo: Repo) -> Optional[str]:
        try:
            return repo.remotes.origin.url if "origin" in repo.remotes else None
        except Exception:
            return None

    @staticmethod
    def _repository_branch(repo: Repo) -> Optional[str]:
        try:
            if not repo.head.is_valid():
                return None
            return repo.head.commit.hexsha[:7] if repo.head.is_detached else repo.active_branch.name
        except Exception:
            return None

    @staticmethod
    def _current_branch_name(repo: Repo) -> tuple[str, bool]:
        if repo.head.is_detached:
            return repo.head.commit.hexsha[:7], True
        return repo.active_branch.name, False

    def _tracking_delta_for_branch(self, repo: Repo, branch: str) -> tuple[int, int]:
        try:
            ahead = len(list(repo.iter_commits(f"origin/{branch}..{branch}")))
            behind = len(list(repo.iter_commits(f"{branch}..origin/{branch}")))
            return ahead, behind
        except Exception:
            return 0, 0

    @staticmethod
    def _change_type(status: str) -> str:
        code = status.strip()[:1]
        if code == "A":
            return "added"
        if code == "D":
            return "deleted"
        if code == "R":
            return "renamed"
        if code == "C":
            return "copied"
        if code == "T":
            return "typechange"
        if code == "U":
            return "unmerged"
        if status == "??":
            return "untracked"
        return "modified"

    def _diff_stats(self, repo: Repo, path: str, *, cached: bool = False) -> tuple[int, int]:
        args = ["--numstat"]
        if cached:
            args.append("--cached")
        args.extend(["--", path])
        try:
            output = repo.git.diff(*args)
        except GitCommandError:
            return 0, 0
        additions = deletions = 0
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                additions += int(parts[0]) if parts[0].isdigit() else 0
                deletions += int(parts[1]) if parts[1].isdigit() else 0
        return additions, deletions

    def _file_change(self, repo: Repo, path: str, status: str, *, cached: bool = False) -> TemplateFileChange:
        additions, deletions = self._diff_stats(repo, path, cached=cached)
        return TemplateFileChange(
            name=Path(path).name,
            path=path,
            status=status,
            type=self._change_type(status),
            additions=additions,
            deletions=deletions,
        )

    def _staged_file_changes(self, repo: Repo) -> list[TemplateFileChange]:
        try:
            output = repo.git.diff("--cached", "--name-status")
        except GitCommandError:
            return []
        changes = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                changes.append(self._file_change(repo, parts[-1], parts[0][:1] or "M", cached=True))
        return changes

    def _has_staged_changes(self, repo: Repo) -> bool:
        return bool(self._staged_file_changes(repo))

    def _commit_staged(
        self,
        kb: db_models.KnowledgeBase,
        repo: Repo,
        *,
        message: str,
    ) -> TemplateCommitResponse:
        if not self._has_staged_changes(repo):
            raise ValueError("GIT_NO_CHANGES")
        commit = repo.index.commit(message)
        kb.git_last_commit_sha = commit.hexsha
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)
        return TemplateCommitResponse(commit=self._commit_summary(repo, commit))

    def _commit_summary(self, repo: Repo, commit: Any) -> TemplateCommitSummary:
        stats = commit.stats.total
        branch, _ = self._current_branch_name(repo)
        return TemplateCommitSummary(
            id=commit.hexsha,
            message=commit.message.strip().splitlines()[0] if commit.message else "",
            author=commit.author.name,
            email=commit.author.email,
            timestamp=int(commit.committed_date * 1000),
            branch=branch,
            additions=stats.get("insertions", 0),
            deletions=stats.get("deletions", 0),
            files=stats.get("files", 0),
        )

    def _branch_commit_info(self, ref: Any) -> Optional[TemplateBranchCommitInfo]:
        try:
            commit = ref.commit
            return TemplateBranchCommitInfo(
                id=commit.hexsha,
                message=commit.message.strip().splitlines()[0] if commit.message else "",
                author=commit.author.name,
                email=commit.author.email,
                timestamp=datetime.fromtimestamp(commit.committed_date, timezone.utc).isoformat(),
            )
        except Exception:
            return None

    def _untracked_file_diff(self, kb_id: str, path: str) -> str:
        file_path = self._kb_root(kb_id) / path
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Binary files /dev/null and b/{path} differ\n"
        return "".join(difflib.unified_diff([], content.splitlines(keepends=True), fromfile="/dev/null", tofile=f"b/{path}", lineterm=""))

    @staticmethod
    def _conflict_files(repo: Repo) -> list[str]:
        conflicts = []
        for item in repo.index.entries:
            if repo.index.entries[item].stage != 0:
                conflicts.append(item[0])
        return conflicts
