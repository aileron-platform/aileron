"""Git status and branch operations

Provides Git status query and branch management functionality.
"""

from __future__ import annotations

import logging
from datetime import timezone
from typing import Optional, TYPE_CHECKING

from git import GitCommandError

from .cache import CacheKeys
from .models import (
    BranchCommitInfo,
    BranchInfo,
    BranchListResponse,
    CheckoutRequest,
    CheckoutResponse,
    VersionControlStatus,
)
from .snapshot import WorkingTreeSnapshotProvider
from .utils import GitUtils, VersionControlError

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class StatusOperations:
    """Git status and branch operations

    Provides functionality such as status query, branch list, branch checkout.
    """

    def __init__(
        self,
        utils: GitUtils,
        cache: Optional["GitCache"] = None,
        snapshot_provider: Optional[WorkingTreeSnapshotProvider] = None,
    ) -> None:
        """Initialize

        Args:
            utils: Git utility class instance
            cache: Cache layer (optional)
        """
        self._utils = utils
        self.cache = cache
        self._snapshot_provider = snapshot_provider or WorkingTreeSnapshotProvider(utils, cache)

    def get_status(self, workspace_id: str, context_id: Optional[str] = None) -> VersionControlStatus:
        """Get Git status

        Args:
            workspace_id: Workspace ID

        Returns:
            Version control status
        """
        snapshot = self._snapshot_provider.get_snapshot(workspace_id, context_id=context_id)
        return VersionControlStatus(
            branch=snapshot.branch,
            ahead=snapshot.ahead,
            behind=snapshot.behind,
            detached=snapshot.detached,
            hasConflicts=snapshot.hasConflicts,
            stagedCount=len(snapshot.staged),
            unstagedCount=len(snapshot.unstaged),
            untrackedCount=snapshot.untrackedTotal,
            lastFetchedAt=snapshot.lastFetchedAt,
        )

    def list_branches(
        self,
        workspace_id: str,
        include_remote: bool = True,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
        include_metadata: bool = True,
    ) -> BranchListResponse:
        """List branches

        Args:
            workspace_id: Workspace ID
            include_remote: Whether to include remote branches
            search: Search keyword

        Returns:
            Branch list response
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        current_branch, detached = self._utils.current_branch(repo)
        query = search.lower() if search else None
        branches: list[BranchInfo] = []

        for branch in repo.branches:
            if query and query not in branch.name.lower():
                continue
            ahead, behind = 0, 0
            if include_metadata:
                tracking = branch.tracking_branch()
                if tracking:
                    try:
                        ahead = sum(1 for _ in repo.iter_commits(f"{tracking}..{branch}"))
                        behind = sum(1 for _ in repo.iter_commits(f"{branch}..{tracking}"))
                    except GitCommandError:
                        ahead = behind = 0
            last_commit = None
            if include_metadata:
                try:
                    commit = branch.commit
                    last_commit = BranchCommitInfo(
                        id=commit.hexsha,
                        message=commit.message.strip(),
                        author=commit.author.name,
                        email=getattr(commit.author, "email", None),
                        timestamp=commit.committed_datetime.replace(tzinfo=timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    )
                except ValueError:
                    last_commit = None
            branches.append(
                BranchInfo(
                    name=branch.name,
                    displayName=branch.name,
                    isActive=(branch.name == current_branch and not detached),
                    isRemote=False,
                    ahead=ahead,
                    behind=behind,
                    lastCommit=last_commit,
                )
            )

        if include_remote:
            # Collect local branch names to avoid duplicate display
            local_branch_names = {b.name for b in branches}

            for remote in repo.remotes:
                for ref in remote.refs:
                    fullname = ref.name

                    # Skip HEAD reference (e.g., origin/HEAD)
                    if ref.remote_head == "HEAD":
                        continue

                    # Skip if local branch corresponding to remote branch already exists
                    if ref.remote_head in local_branch_names:
                        continue

                    if query and query not in fullname.lower():
                        continue

                    # Use full name as displayName to avoid confusion with local branches
                    branches.append(
                        BranchInfo(
                            name=fullname,
                            displayName=fullname,
                            isActive=False,
                            isRemote=True,
                            ahead=0,
                            behind=0,
                            lastCommit=None,
                        )
                    )

        return BranchListResponse(branches=branches)

    def checkout_branch(
        self, workspace_id: str, branch_name: str, payload: CheckoutRequest, context_id: Optional[str] = None
    ) -> CheckoutResponse:
        """Checkout branch

        Args:
            workspace_id: Workspace ID
            branch_name: Target branch name
            payload: Checkout request

        Returns:
            Checkout response

        Raises:
            VersionControlError: Checkout failed
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        stashed = None

        if payload.stashChanges:
            try:
                stashed = repo.git.stash("push", "-u")
            except GitCommandError as exc:
                raise VersionControlError(str(exc), error_code="VC_STASH_FAILED") from exc

        try:
            if payload.create:
                args = ["-b", branch_name]
                if payload.startPoint:
                    args.append(payload.startPoint)
                repo.git.checkout(*args)
                created = True
            else:
                repo.git.checkout(branch_name)
                created = False
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_BRANCH_CHECKOUT_FAILED") from exc

        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)
            self.cache.invalidate(workspace_id, CacheKeys.BRANCHES)
            self.cache.invalidate(workspace_id, CacheKeys.COMMITS)

        return CheckoutResponse(
            branch=branch_name,
            created=created,
            stashedChanges=stashed if stashed else None,
        )


__all__ = ["StatusOperations"]
