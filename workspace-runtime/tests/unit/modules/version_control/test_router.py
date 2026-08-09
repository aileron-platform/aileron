from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.models import (
    BranchCapabilities,
    BranchCapability,
    BranchInfo,
    BranchListResponse,
    ChangePage,
    ChangesResponse,
    CommitListItem,
    CommitListResponse,
    FileChange,
    StageResponse,
    VersionControlOperationStatus,
    VersionControlStatus,
)
from app.modules.version_control.repository import VersionControlError
from app.modules.version_control.router import router


class DummyGitService:
    def __init__(self) -> None:
        self.error: VersionControlError | None = None
        self.changes_call: dict | None = None
        self.history_call: dict | None = None

    def _raise_if_needed(self) -> None:
        if self.error is not None:
            raise self.error

    def get_status(self, workspace_id: str, context_id: str | None = None):
        self._raise_if_needed()
        return VersionControlStatus(
            isInitialized=True,
            currentBranch="main",
            detachedHead=False,
            headSha="a" * 40,
        )

    def get_operation_status(
        self, workspace_id: str, context_id: str | None = None
    ) -> VersionControlOperationStatus:
        self._raise_if_needed()
        return VersionControlOperationStatus(isActive=False)

    def list_branches(self, workspace_id: str, **kwargs):
        self._raise_if_needed()
        return BranchListResponse(
            branches=[
                BranchInfo(
                    name="main",
                    displayName="main",
                    kind="local",
                    isCurrent=True,
                    capabilities=BranchCapabilities(
                        switch=BranchCapability(allowed=False),
                        rename=BranchCapability(allowed=True),
                        delete=BranchCapability(allowed=False),
                    ),
                )
            ]
        )

    def get_changes(self, workspace_id: str, **kwargs):
        self._raise_if_needed()
        self.changes_call = kwargs
        return ChangesResponse(
            staged=ChangePage(
                items=[
                    FileChange(
                        name="a.py", path="a.py", status="A ", type="added"
                    )
                ],
                total=2,
                nextCursor="1",
                hasMore=True,
            )
        )

    def list_commits(self, workspace_id: str, **kwargs):
        self._raise_if_needed()
        self.history_call = kwargs
        return CommitListResponse(
            items=[
                CommitListItem(
                    id="a" * 40,
                    message="init",
                    author="Tester",
                    timestamp=1,
                    branch="main",
                    additions=1,
                    deletions=0,
                    files=1,
                )
            ],
            total=2,
            nextCursor="1",
            hasMore=True,
            queryScope=kwargs["query_scope"],
        )

    def stage(self, workspace_id: str, payload, context_id: str | None = None):
        self._raise_if_needed()
        return StageResponse(staged=list(payload.paths), unstaged=[])


def _client(service: DummyGitService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_git_service] = lambda: service
    return TestClient(app)


def test_status_uses_exact_repository_status_contract() -> None:
    response = _client(DummyGitService()).get("/workspaces/ws/version-control/status")

    assert response.status_code == 200
    assert response.json() == {
        "isInitialized": True,
        "currentBranch": "main",
        "detachedHead": False,
        "headSha": "a" * 40,
        "hasOrigin": False,
        "upstream": None,
        "ahead": 0,
        "behind": 0,
        "hasConflicts": False,
        "stagedTotal": 0,
        "unstagedTotal": 0,
        "untrackedTotal": 0,
        "conflictTotal": 0,
        "operationStatus": None,
    }
    assert "branch" not in response.json()
    assert "stagedCount" not in response.json()


def test_changes_forwards_cursor_query_and_returns_independent_pages() -> None:
    service = DummyGitService()
    response = _client(service).get(
        "/workspaces/ws/version-control/changes",
        params={"group": "staged", "cursor": "4", "limit": 25, "includeStats": False},
    )

    assert response.status_code == 200
    assert response.json()["staged"]["nextCursor"] == "1"
    assert response.json()["unstaged"] == {
        "items": [],
        "total": 0,
        "nextCursor": None,
        "hasMore": False,
    }
    assert service.changes_call == {
        "group": "staged",
        "cursor": "4",
        "limit": 25,
        "context_id": None,
        "include_stats": False,
    }


def test_history_forwards_cursor_scope_and_returns_contract_page() -> None:
    service = DummyGitService()
    response = _client(service).get(
        "/workspaces/ws/version-control/commits",
        params={
            "cursor": "20",
            "limit": 10,
            "queryScope": "local",
            "branch": "develop",
            "search": "fix",
        },
    )

    assert response.status_code == 200
    assert response.json()["queryScope"] == "local"
    assert response.json()["nextCursor"] == "1"
    assert "page" not in response.json()
    assert service.history_call == {
        "cursor": "20",
        "limit": 10,
        "query_scope": "local",
        "branch": "develop",
        "search": "fix",
        "context_id": None,
    }


def test_stage_rejects_forbidden_include_untracked_field() -> None:
    response = _client(DummyGitService()).post(
        "/workspaces/ws/version-control/stage",
        json={"paths": ["a.py"], "includeUntracked": True},
    )

    assert response.status_code == 422


def test_router_serializes_shared_error_envelope() -> None:
    service = DummyGitService()
    service.error = VersionControlError(
        "locked",
        status_code=409,
        error_code="operation_locked",
        blocking_scope="working_tree_target",
        stale=False,
        can_force_unlock=False,
    )

    response = _client(service).get("/workspaces/ws/version-control/status")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "errorCode": "operation_locked",
        "messageKey": "operation_locked",
        "blockingScope": "working_tree_target",
        "operationStatus": None,
        "stale": False,
        "canForceUnlock": False,
    }
