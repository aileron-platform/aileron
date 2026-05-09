from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.version_control.models import (
    BlobResponse,
    BranchInfo,
    BranchListResponse,
    ChangesResponse,
    CheckoutRequest,
    CheckoutResponse,
    CommitAuthor,
    CommitDetailResponse,
    CommitFilesResponse,
    CommitListItem,
    CommitListResponse,
    CommitRequest,
    CommitResponse,
    CommitStats,
    DiffResponse,
    DiscardRequest,
    DiscardResponse,
    FetchRequest,
    FetchResponse,
    FileChange,
    GitContext,
    GitContextListResponse,
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    PushUpdate,
    RemoteSettingsRequest,
    RemoteSettingsResponse,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlStatus,
)
from app.modules.version_control.router import (
    _handle_error,
    checkout_branch,
    create_commit,
    discard_changes,
    fetch_changes,
    get_blob,
    get_changes,
    get_commit,
    get_commit_files,
    get_diff,
    get_remote_settings,
    get_status,
    list_contexts,
    list_branches,
    list_commits,
    pull_changes,
    push_changes,
    set_remote_settings,
    stage_changes,
    unstage_changes,
)
from app.modules.version_control.service import VersionControlError


class DummyGitService:
    def __init__(self) -> None:
        self.error: VersionControlError | None = None

    def _maybe_raise(self) -> None:
        if self.error:
            raise self.error

    def list_contexts(self, workspace_id: str) -> GitContextListResponse:
        self._maybe_raise()
        return GitContextListResponse(
            activeContextId="primary",
            contexts=[GitContext(id="primary", kind="primary", displayName="main", repoPath="/workspace", detached=False, locked=False, prunable=False)],
        )

    def get_status(self, workspace_id: str, context_id: str | None = None) -> VersionControlStatus:
        self._maybe_raise()
        return VersionControlStatus(branch="main")

    def list_branches(
        self,
        workspace_id: str,
        include_remote: bool = True,
        search: str | None = None,
        context_id: str | None = None,
        include_metadata: bool = True,
    ) -> BranchListResponse:
        self._maybe_raise()
        return BranchListResponse(branches=[BranchInfo(name="main", displayName="main", isActive=True, isRemote=False)])

    def checkout_branch(self, workspace_id: str, branch_name: str, payload: CheckoutRequest, context_id: str | None = None) -> CheckoutResponse:
        self._maybe_raise()
        return CheckoutResponse(branch=branch_name, created=payload.create)

    def get_changes(self, workspace_id: str, page: int = 1, page_size: int = 100, context_id: str | None = None) -> ChangesResponse:
        self._maybe_raise()
        return ChangesResponse(
            staged=[FileChange(name="a.py", path="a.py", status="A", type="added")],
            unstaged=[FileChange(name="b.py", path="b.py", status="M", type="modified")],
            untracked=[FileChange(name="c.py", path="c.py", status="?", type="untracked")],
            untrackedTotal=1,
            untrackedPage=page,
            untrackedPageSize=page_size,
            untrackedHasMore=False,
        )

    def stage(self, workspace_id: str, payload: StageRequest, context_id: str | None = None) -> StageResponse:
        self._maybe_raise()
        return StageResponse(staged=payload.paths, unstaged=[])

    def unstage(self, workspace_id: str, payload: UnstageRequest, context_id: str | None = None) -> UnstageResponse:
        self._maybe_raise()
        return UnstageResponse(unstaged=payload.paths, remainingStaged=0)

    def discard(self, workspace_id: str, payload: DiscardRequest, context_id: str | None = None) -> DiscardResponse:
        self._maybe_raise()
        return DiscardResponse(discarded=payload.paths)

    def commit(self, workspace_id: str, payload: CommitRequest, context_id: str | None = None) -> CommitResponse:
        self._maybe_raise()
        return CommitResponse(
            commit={
                "id": "a" * 40,
                "message": payload.message,
                "author": CommitAuthor(name="Test", email="test@example.com"),
                "timestamp": "2024-01-01T00:00:00Z",
                "additions": 1,
                "deletions": 0,
            }
        )

    def list_commits(self, workspace_id: str, page: int = 1, page_size: int = 20, branch: str | None = None, search: str | None = None, context_id: str | None = None) -> CommitListResponse:
        self._maybe_raise()
        return CommitListResponse(
            page=page,
            pageSize=page_size,
            total=1,
            items=[CommitListItem(id="a" * 40, message="init", author="Test", email="test@example.com", timestamp=1, branch="main", additions=1, deletions=0, files=1)],
        )

    def get_commit(self, workspace_id: str, commit_id: str, context_id: str | None = None) -> CommitDetailResponse:
        self._maybe_raise()
        return CommitDetailResponse(
            id=commit_id,
            message="init",
            author=CommitAuthor(name="Test", email="test@example.com"),
            timestamp="2024-01-01T00:00:00Z",
            branch="main",
            stats=CommitStats(additions=1, deletions=0, files=1),
            changes=[],
        )

    def get_commit_files(self, workspace_id: str, commit_id: str, context_id: str | None = None) -> CommitFilesResponse:
        self._maybe_raise()
        return CommitFilesResponse(commitId=commit_id, files=[])

    def push(self, workspace_id: str, payload: PushRequest, context_id: str | None = None) -> PushResponse:
        self._maybe_raise()
        return PushResponse(remote=payload.remote, branch=payload.branch or "main", updates=[PushUpdate(ref="refs/heads/main", status="ok")])

    def pull(self, workspace_id: str, payload: PullRequest, context_id: str | None = None) -> PullResponse:
        self._maybe_raise()
        return PullResponse(remote=payload.remote, branch=payload.branch or "main", fastForward=True, commits=[])

    def fetch(self, workspace_id: str, payload: FetchRequest, context_id: str | None = None) -> FetchResponse:
        self._maybe_raise()
        return FetchResponse(remote=payload.remote, fetchedRefs=["refs/heads/main"])

    def get_remote_settings(self, workspace_id: str, context_id: str | None = None) -> RemoteSettingsResponse:
        self._maybe_raise()
        return RemoteSettingsResponse(
            isInitialized=True,
            currentBranch="main",
            remoteUrl="git@example.com:team/project.git",
            hasOrigin=True,
        )

    def set_remote_settings(
        self,
        workspace_id: str,
        payload: RemoteSettingsRequest,
        context_id: str | None = None,
    ) -> RemoteSettingsResponse:
        self._maybe_raise()
        return RemoteSettingsResponse(
            isInitialized=True,
            currentBranch="main",
            remoteUrl=payload.remote_url,
            hasOrigin=True,
        )

    def diff(self, workspace_id: str, path: str, base: str | None = None, head: str | None = None, context: int = 3, include_metadata: bool = False, context_id: str | None = None) -> DiffResponse:
        self._maybe_raise()
        return DiffResponse(path=path, base=base or "HEAD", head=head or "WORKTREE", context=context, patch="@@ -1 +1 @@", metadata={"ok": True} if include_metadata else None)

    def blob(self, workspace_id: str, path: str, revision: str | None = None, context_id: str | None = None) -> BlobResponse:
        self._maybe_raise()
        return BlobResponse(path=path, revision=revision or "HEAD", content="ZmlsZQ==")


def test_handle_error_maps_exception() -> None:
    exc = _handle_error(VersionControlError("boom", status_code=409, error_code="X"))
    assert exc.status_code == 409
    assert exc.detail["errorCode"] == "X"


@pytest.mark.asyncio
async def test_router_success_paths() -> None:
    service = DummyGitService()

    assert (await list_contexts("ws", service)).activeContextId == "primary"
    assert (await get_status("ws", None, service)).branch == "main"
    assert len((await list_branches("ws", True, None, True, None, service)).branches) == 1
    assert (await checkout_branch(CheckoutRequest(create=True), "ws", "feature/x", None, service)).created is True
    assert len((await get_changes("ws", "all", 1, 100, None, service)).staged) == 1
    assert len((await get_changes("ws", "staged", 1, 100, None, service)).unstaged) == 0
    assert len((await get_changes("ws", "unstaged", 1, 100, None, service)).staged) == 0
    assert len((await get_changes("ws", "untracked", 1, 100, None, service)).untracked) == 1
    assert (await stage_changes(StageRequest(paths=["a.py"]), "ws", None, service)).staged == ["a.py"]
    assert (await unstage_changes(UnstageRequest(paths=["a.py"]), "ws", None, service)).unstaged == ["a.py"]
    assert (await discard_changes(DiscardRequest(paths=["a.py"]), "ws", None, service)).discarded == ["a.py"]
    assert (await create_commit(CommitRequest(message="msg"), "ws", None, service)).commit.message == "msg"
    assert (await list_commits("ws", 1, 20, None, None, None, service)).total == 1
    assert (await get_commit("ws", "c1", None, service)).id == "c1"
    assert (await get_commit_files("ws", "c1", None, service)).commitId == "c1"
    assert (await push_changes(PushRequest(), "ws", None, service)).remote == "origin"
    assert (await pull_changes(PullRequest(), "ws", None, service)).fastForward is True
    assert (await fetch_changes(FetchRequest(), "ws", None, service)).fetchedRefs == ["refs/heads/main"]
    assert (await get_remote_settings("ws", None, service)).remote_url == "git@example.com:team/project.git"
    assert (await set_remote_settings(RemoteSettingsRequest(remoteUrl="git@example.com:team/updated.git"), "ws", None, service)).remote_url == "git@example.com:team/updated.git"
    assert (await get_diff("ws", "a.py", None, None, 3, True, None, service)).metadata == {"ok": True}
    assert (await get_blob("ws", "a.py", None, None, service)).revision == "HEAD"


@pytest.mark.asyncio
async def test_router_error_path_raises_http_exception() -> None:
    service = DummyGitService()
    service.error = VersionControlError("bad", status_code=404, error_code="NOPE")

    with pytest.raises(HTTPException) as exc_info:
        await get_status("ws", None, service)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_router_preserves_repository_not_initialized_contract() -> None:
    service = DummyGitService()
    service.error = VersionControlError(
        "Workspace is not a git repository",
        status_code=400,
        error_code="VC_REPOSITORY_NOT_INITIALIZED",
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_status("ws", None, service)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["errorCode"] == "VC_REPOSITORY_NOT_INITIALIZED"


@pytest.mark.asyncio
async def test_list_branches_and_get_changes_forward_query_params() -> None:
    service = DummyGitService()

    branches = await list_branches("ws", False, "feature", True, None, service)
    changes = await get_changes("ws", "unknown", 2, 25, None, service)

    assert len(branches.branches) == 1
    assert changes.untrackedPage == 2
    assert changes.untrackedPageSize == 25


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "expected_status"),
    [
        (lambda service: list_branches("ws", True, None, True, None, service), 422),
        (lambda service: checkout_branch(CheckoutRequest(create=False), "ws", "main", None, service), 422),
        (lambda service: get_changes("ws", "all", 1, 100, None, service), 422),
        (lambda service: stage_changes(StageRequest(paths=["a.py"]), "ws", None, service), 422),
        (lambda service: unstage_changes(UnstageRequest(paths=["a.py"]), "ws", None, service), 422),
        (lambda service: discard_changes(DiscardRequest(paths=["a.py"]), "ws", None, service), 422),
        (lambda service: create_commit(CommitRequest(message="msg"), "ws", None, service), 422),
        (lambda service: list_commits("ws", 1, 20, None, None, None, service), 422),
        (lambda service: get_commit("ws", "c1", None, service), 422),
        (lambda service: get_commit_files("ws", "c1", None, service), 422),
        (lambda service: push_changes(PushRequest(), "ws", None, service), 422),
        (lambda service: pull_changes(PullRequest(), "ws", None, service), 422),
        (lambda service: fetch_changes(FetchRequest(), "ws", None, service), 422),
        (lambda service: get_diff("ws", "a.py", None, None, 3, False, None, service), 422),
        (lambda service: get_blob("ws", "a.py", None, None, service), 422),
    ],
)
async def test_router_error_mapping_for_each_endpoint(call, expected_status: int) -> None:
    service = DummyGitService()
    service.error = VersionControlError("bad", status_code=expected_status, error_code="NOPE")

    with pytest.raises(HTTPException) as exc_info:
        await call(service)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail["errorCode"] == "NOPE"
