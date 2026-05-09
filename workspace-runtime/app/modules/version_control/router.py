"""Version control router"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from .models import (
    BlobResponse,
    BranchListResponse,
    ChangesResponse,
    CheckoutRequest,
    CheckoutResponse,
    CommitDetailResponse,
    CommitFilesResponse,
    CommitListResponse,
    CommitRequest,
    CommitResponse,
    DiffResponse,
    DiscardRequest,
    DiscardResponse,
    FetchRequest,
    FetchResponse,
    GitContextListResponse,
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    RemoteSettingsRequest,
    RemoteSettingsResponse,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlStatus,
)
from .dependencies import get_git_service
from .service import GitService, VersionControlError

router = APIRouter(
    prefix="/workspaces/{workspace_id}/version-control",
    tags=["Version control"],
)


def _handle_error(exc: VersionControlError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"errorCode": exc.error_code, "message": str(exc)},
    )


@router.get(
    "/contexts",
    response_model=GitContextListResponse,
    summary="Get Git contexts",
    responses=build_responses(401, 404, 500),
)
async def list_contexts(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> GitContextListResponse:
    try:
        return service.list_contexts(workspace_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/status",
    response_model=VersionControlStatus,
    summary="Get Git status",
    responses=build_responses(401, 404, 500),
)
async def get_status(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> VersionControlStatus:
    try:
        return service.get_status(workspace_id, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/branches",
    response_model=BranchListResponse,
    summary="Get branch list",
    responses=build_responses(401, 404, 422, 500),
)
async def list_branches(
    workspace_id: str = Path(..., description="Workspace ID"),
    include_remote: bool = Query(True, alias="includeRemote", description="Whether to include remotes"),
    search: str | None = Query(None, description="Name filter"),
    include_metadata: bool = Query(True, alias="includeMetadata", description="Whether to include branch statistics and last commit info"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> BranchListResponse:
    try:
        return service.list_branches(
            workspace_id,
            include_remote=include_remote,
            search=search,
            context_id=context_id,
            include_metadata=include_metadata,
        )
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/branches/{branch_name:path}/checkout",
    response_model=CheckoutResponse,
    summary="Switch to or create branch",
    responses=build_responses(400, 401, 404, 422, 409, 500),
)
async def checkout_branch(
    payload: CheckoutRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    branch_name: str = Path(..., description="Target branch"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> CheckoutResponse:
    try:
        return service.checkout_branch(workspace_id, branch_name, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/changes",
    response_model=ChangesResponse,
    summary="Get change list",
    responses=build_responses(401, 404, 422, 500),
)
async def get_changes(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: str = Query("all", description="Filter scope"),
    page: int = Query(1, ge=1, description="Page number (for untracked only)"),
    page_size: int = Query(100, ge=1, le=500, alias="pageSize", description="Items per page"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> ChangesResponse:
    try:
        changes = service.get_changes(workspace_id, page=page, page_size=page_size, context_id=context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)
    scope_lower = scope.lower()
    if scope_lower == "staged":
        return ChangesResponse(
            staged=changes.staged,
            unstaged=[],
            untracked=[],
            untrackedTotal=changes.untrackedTotal,
            untrackedPage=changes.untrackedPage,
            untrackedPageSize=changes.untrackedPageSize,
            untrackedHasMore=changes.untrackedHasMore,
        )
    if scope_lower == "unstaged":
        return ChangesResponse(
            staged=[],
            unstaged=changes.unstaged,
            untracked=[],
            untrackedTotal=changes.untrackedTotal,
            untrackedPage=changes.untrackedPage,
            untrackedPageSize=changes.untrackedPageSize,
            untrackedHasMore=changes.untrackedHasMore,
        )
    if scope_lower == "untracked":
        return ChangesResponse(
            staged=[],
            unstaged=[],
            untracked=changes.untracked,
            untrackedTotal=changes.untrackedTotal,
            untrackedPage=changes.untrackedPage,
            untrackedPageSize=changes.untrackedPageSize,
            untrackedHasMore=changes.untrackedHasMore,
        )
    return changes


@router.post(
    "/stage",
    response_model=StageResponse,
    summary="Stage files",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def stage_changes(
    payload: StageRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> StageResponse:
    try:
        return service.stage(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/unstage",
    response_model=UnstageResponse,
    summary="Unstage files",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def unstage_changes(
    payload: UnstageRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> UnstageResponse:
    try:
        return service.unstage(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/discard",
    response_model=DiscardResponse,
    summary="Discard unstaged changes",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def discard_changes(
    payload: DiscardRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> DiscardResponse:
    try:
        return service.discard(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/commit",
    response_model=CommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create commit",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def create_commit(
    payload: CommitRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> CommitResponse:
    try:
        return service.commit(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/commits",
    response_model=CommitListResponse,
    summary="List commit history",
    responses=build_responses(401, 404, 422, 500),
)
async def list_commits(
    workspace_id: str = Path(..., description="Workspace ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    branch: str | None = Query(None, description="Branch name"),
    search: str | None = Query(None, description="Search keyword"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> CommitListResponse:
    try:
        return service.list_commits(workspace_id, page=page, page_size=page_size, branch=branch, search=search, context_id=context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/commits/{commit_id}",
    response_model=CommitDetailResponse,
    summary="Get commit details",
    responses=build_responses(401, 404, 500),
)
async def get_commit(
    workspace_id: str = Path(..., description="Workspace ID"),
    commit_id: str = Path(..., description="Commit ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> CommitDetailResponse:
    try:
        return service.get_commit(workspace_id, commit_id, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/commits/{commit_id}/files",
    response_model=CommitFilesResponse,
    summary="Get commit file differences",
    responses=build_responses(401, 404, 500),
)
async def get_commit_files(
    workspace_id: str = Path(..., description="Workspace ID"),
    commit_id: str = Path(..., description="Commit ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> CommitFilesResponse:
    try:
        return service.get_commit_files(workspace_id, commit_id, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/push",
    response_model=PushResponse,
    summary="Push to remote",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def push_changes(
    payload: PushRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> PushResponse:
    try:
        return service.push(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/pull",
    response_model=PullResponse,
    summary="Pull remote updates",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def pull_changes(
    payload: PullRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> PullResponse:
    try:
        return service.pull(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/fetch",
    response_model=FetchResponse,
    summary="Sync remote references",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def fetch_changes(
    payload: FetchRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> FetchResponse:
    try:
        return service.fetch(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/remote",
    response_model=RemoteSettingsResponse,
    summary="Get remote settings",
    responses=build_responses(401, 404, 500),
)
async def get_remote_settings(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> RemoteSettingsResponse:
    try:
        return service.get_remote_settings(workspace_id, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.put(
    "/remote",
    response_model=RemoteSettingsResponse,
    summary="Set remote settings",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def set_remote_settings(
    payload: RemoteSettingsRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> RemoteSettingsResponse:
    try:
        return service.set_remote_settings(workspace_id, payload, context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/diff",
    response_model=DiffResponse,
    summary="Get diff",
    responses=build_responses(401, 404, 422, 500),
)
async def get_diff(
    workspace_id: str = Path(..., description="Workspace ID"),
    path: str = Query(..., description="File path"),
    base: str | None = Query(None, description="Comparison base"),
    head: str | None = Query(None, description="Comparison target"),
    context: int = Query(3, ge=0, description="Context line count"),
    include_metadata: bool = Query(False, alias="includeMetadata", description="Whether to include metadata"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> DiffResponse:
    try:
        return service.diff(
            workspace_id,
            path=path,
            base=base,
            head=head,
            context=context,
            include_metadata=include_metadata,
            context_id=context_id,
        )
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/blob",
    response_model=BlobResponse,
    summary="Read file content at specified version",
    responses=build_responses(401, 404, 422, 500),
)
async def get_blob(
    workspace_id: str = Path(..., description="Workspace ID"),
    path: str = Query(..., description="File path"),
    revision: str | None = Query(None, description="Commit or reference"),
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
    service: GitService = Depends(get_git_service),
) -> BlobResponse:
    try:
        return service.blob(workspace_id, path=path, revision=revision, context_id=context_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


__all__ = ["router"]
