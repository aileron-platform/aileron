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
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    PushUpdate,
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
    get_status,
    list_branches,
    list_commits,
    pull_changes,
    push_changes,
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

    def get_status(self, workspace_id: str) -> VersionControlStatus:
        self._maybe_raise()
        return VersionControlStatus(branch="main")

    def list_branches(self, workspace_id: str, include_remote: bool = True, search: str | None = None) -> BranchListResponse:
        self._maybe_raise()
        return BranchListResponse(branches=[BranchInfo(name="main", displayName="main", isActive=True, isRemote=False)])

    def checkout_branch(self, workspace_id: str, branch_name: str, payload: CheckoutRequest) -> CheckoutResponse:
        self._maybe_raise()
        return CheckoutResponse(branch=branch_name, created=payload.create)

    def get_changes(self, workspace_id: str, page: int = 1, page_size: int = 100) -> ChangesResponse:
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

    def stage(self, workspace_id: str, payload: StageRequest) -> StageResponse:
        self._maybe_raise()
        return StageResponse(staged=payload.paths, unstaged=[])

    def unstage(self, workspace_id: str, payload: UnstageRequest) -> UnstageResponse:
        self._maybe_raise()
        return UnstageResponse(unstaged=payload.paths, remainingStaged=0)

    def discard(self, workspace_id: str, payload: DiscardRequest) -> DiscardResponse:
        self._maybe_raise()
        return DiscardResponse(discarded=payload.paths)

    def commit(self, workspace_id: str, payload: CommitRequest) -> CommitResponse:
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

    def list_commits(self, workspace_id: str, page: int = 1, page_size: int = 20, branch: str | None = None, search: str | None = None) -> CommitListResponse:
        self._maybe_raise()
        return CommitListResponse(
            page=page,
            pageSize=page_size,
            total=1,
            items=[CommitListItem(id="a" * 40, message="init", author="Test", email="test@example.com", timestamp=1, branch="main", additions=1, deletions=0, files=1)],
        )

    def get_commit(self, workspace_id: str, commit_id: str) -> CommitDetailResponse:
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

    def get_commit_files(self, workspace_id: str, commit_id: str) -> CommitFilesResponse:
        self._maybe_raise()
        return CommitFilesResponse(commitId=commit_id, files=[])

    def push(self, workspace_id: str, payload: PushRequest) -> PushResponse:
        self._maybe_raise()
        return PushResponse(remote=payload.remote, branch=payload.branch or "main", updates=[PushUpdate(ref="refs/heads/main", status="ok")])

    def pull(self, workspace_id: str, payload: PullRequest) -> PullResponse:
        self._maybe_raise()
        return PullResponse(remote=payload.remote, branch=payload.branch or "main", fastForward=True, commits=[])

    def fetch(self, workspace_id: str, payload: FetchRequest) -> FetchResponse:
        self._maybe_raise()
        return FetchResponse(remote=payload.remote, fetchedRefs=["refs/heads/main"])

    def diff(self, workspace_id: str, path: str, base: str | None = None, head: str | None = None, context: int = 3, include_metadata: bool = False) -> DiffResponse:
        self._maybe_raise()
        return DiffResponse(path=path, base=base or "HEAD", head=head or "WORKTREE", context=context, patch="@@ -1 +1 @@", metadata={"ok": True} if include_metadata else None)

    def blob(self, workspace_id: str, path: str, revision: str | None = None) -> BlobResponse:
        self._maybe_raise()
        return BlobResponse(path=path, revision=revision or "HEAD", content="ZmlsZQ==")


def test_handle_error_maps_exception() -> None:
    exc = _handle_error(VersionControlError("boom", status_code=409, error_code="X"))
    assert exc.status_code == 409
    assert exc.detail["errorCode"] == "X"


@pytest.mark.asyncio
async def test_router_success_paths() -> None:
    service = DummyGitService()

    assert (await get_status("ws", service)).branch == "main"
    assert len((await list_branches("ws", True, None, service)).branches) == 1
    assert (await checkout_branch(CheckoutRequest(create=True), "ws", "feature/x", service)).created is True
    assert len((await get_changes("ws", "all", 1, 100, service)).staged) == 1
    assert len((await get_changes("ws", "staged", 1, 100, service)).unstaged) == 0
    assert len((await get_changes("ws", "unstaged", 1, 100, service)).staged) == 0
    assert len((await get_changes("ws", "untracked", 1, 100, service)).untracked) == 1
    assert (await stage_changes(StageRequest(paths=["a.py"]), "ws", service)).staged == ["a.py"]
    assert (await unstage_changes(UnstageRequest(paths=["a.py"]), "ws", service)).unstaged == ["a.py"]
    assert (await discard_changes(DiscardRequest(paths=["a.py"]), "ws", service)).discarded == ["a.py"]
    assert (await create_commit(CommitRequest(message="msg"), "ws", service)).commit.message == "msg"
    assert (await list_commits("ws", 1, 20, None, None, service)).total == 1
    assert (await get_commit("ws", "c1", service)).id == "c1"
    assert (await get_commit_files("ws", "c1", service)).commitId == "c1"
    assert (await push_changes(PushRequest(), "ws", service)).remote == "origin"
    assert (await pull_changes(PullRequest(), "ws", service)).fastForward is True
    assert (await fetch_changes(FetchRequest(), "ws", service)).fetchedRefs == ["refs/heads/main"]
    assert (await get_diff("ws", "a.py", None, None, 3, True, service)).metadata == {"ok": True}
    assert (await get_blob("ws", "a.py", None, service)).revision == "HEAD"


@pytest.mark.asyncio
async def test_router_error_path_raises_http_exception() -> None:
    service = DummyGitService()
    service.error = VersionControlError("bad", status_code=404, error_code="NOPE")

    with pytest.raises(HTTPException) as exc_info:
        await get_status("ws", service)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_branches_and_get_changes_forward_query_params() -> None:
    service = DummyGitService()

    branches = await list_branches("ws", False, "feature", service)
    changes = await get_changes("ws", "unknown", 2, 25, service)

    assert len(branches.branches) == 1
    assert changes.untrackedPage == 2
    assert changes.untrackedPageSize == 25


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "expected_status"),
    [
        (lambda service: list_branches("ws", True, None, service), 422),
        (lambda service: checkout_branch(CheckoutRequest(create=False), "ws", "main", service), 422),
        (lambda service: get_changes("ws", "all", 1, 100, service), 422),
        (lambda service: stage_changes(StageRequest(paths=["a.py"]), "ws", service), 422),
        (lambda service: unstage_changes(UnstageRequest(paths=["a.py"]), "ws", service), 422),
        (lambda service: discard_changes(DiscardRequest(paths=["a.py"]), "ws", service), 422),
        (lambda service: create_commit(CommitRequest(message="msg"), "ws", service), 422),
        (lambda service: list_commits("ws", 1, 20, None, None, service), 422),
        (lambda service: get_commit("ws", "c1", service), 422),
        (lambda service: get_commit_files("ws", "c1", service), 422),
        (lambda service: push_changes(PushRequest(), "ws", service), 422),
        (lambda service: pull_changes(PullRequest(), "ws", service), 422),
        (lambda service: fetch_changes(FetchRequest(), "ws", service), 422),
        (lambda service: get_diff("ws", "a.py", None, None, 3, False, service), 422),
        (lambda service: get_blob("ws", "a.py", None, service), 422),
    ],
)
async def test_router_error_mapping_for_each_endpoint(call, expected_status: int) -> None:
    service = DummyGitService()
    service.error = VersionControlError("bad", status_code=expected_status, error_code="NOPE")

    with pytest.raises(HTTPException) as exc_info:
        await call(service)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail["errorCode"] == "NOPE"
