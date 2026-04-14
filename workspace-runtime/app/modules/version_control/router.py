"""版本控制路由"""

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
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
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
    tags=["版本控制"],
)


def _handle_error(exc: VersionControlError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"errorCode": exc.error_code, "message": str(exc)},
    )


@router.get(
    "/status",
    response_model=VersionControlStatus,
    summary="取得 Git 狀態",
    responses=build_responses(401, 404, 500),
)
async def get_status(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> VersionControlStatus:
    try:
        return service.get_status(workspace_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/branches",
    response_model=BranchListResponse,
    summary="取得分支列表",
    responses=build_responses(401, 404, 422, 500),
)
async def list_branches(
    workspace_id: str = Path(..., description="Workspace ID"),
    include_remote: bool = Query(True, alias="includeRemote", description="是否包含遠端"),
    search: str | None = Query(None, description="名稱過濾"),
    service: GitService = Depends(get_git_service),
) -> BranchListResponse:
    try:
        return service.list_branches(workspace_id, include_remote=include_remote, search=search)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/branches/{branch_name:path}/checkout",
    response_model=CheckoutResponse,
    summary="切換或建立分支",
    responses=build_responses(400, 401, 404, 422, 409, 500),
)
async def checkout_branch(
    payload: CheckoutRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    branch_name: str = Path(..., description="目標分支"),
    service: GitService = Depends(get_git_service),
) -> CheckoutResponse:
    try:
        return service.checkout_branch(workspace_id, branch_name, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/changes",
    response_model=ChangesResponse,
    summary="取得變更列表",
    responses=build_responses(401, 404, 422, 500),
)
async def get_changes(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: str = Query("all", description="過濾範圍"),
    page: int = Query(1, ge=1, description="頁碼(僅用於 untracked)"),
    page_size: int = Query(100, ge=1, le=500, alias="pageSize", description="每頁數量"),
    service: GitService = Depends(get_git_service),
) -> ChangesResponse:
    try:
        changes = service.get_changes(workspace_id, page=page, page_size=page_size)
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
    summary="暫存檔案",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def stage_changes(
    payload: StageRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> StageResponse:
    try:
        return service.stage(workspace_id, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/unstage",
    response_model=UnstageResponse,
    summary="取消暫存",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def unstage_changes(
    payload: UnstageRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> UnstageResponse:
    try:
        return service.unstage(workspace_id, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/discard",
    response_model=DiscardResponse,
    summary="丟棄未暫存變更",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def discard_changes(
    payload: DiscardRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> DiscardResponse:
    try:
        return service.discard(workspace_id, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/commit",
    response_model=CommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立提交",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def create_commit(
    payload: CommitRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> CommitResponse:
    try:
        return service.commit(workspace_id, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/commits",
    response_model=CommitListResponse,
    summary="列出提交紀錄",
    responses=build_responses(401, 404, 422, 500),
)
async def list_commits(
    workspace_id: str = Path(..., description="Workspace ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    branch: str | None = Query(None, description="分支名稱"),
    search: str | None = Query(None, description="搜尋關鍵字"),
    service: GitService = Depends(get_git_service),
) -> CommitListResponse:
    try:
        return service.list_commits(workspace_id, page=page, page_size=page_size, branch=branch, search=search)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/commits/{commit_id}",
    response_model=CommitDetailResponse,
    summary="取得提交詳細",
    responses=build_responses(401, 404, 500),
)
async def get_commit(
    workspace_id: str = Path(..., description="Workspace ID"),
    commit_id: str = Path(..., description="提交 ID"),
    service: GitService = Depends(get_git_service),
) -> CommitDetailResponse:
    try:
        return service.get_commit(workspace_id, commit_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/commits/{commit_id}/files",
    response_model=CommitFilesResponse,
    summary="取得提交檔案差異",
    responses=build_responses(401, 404, 500),
)
async def get_commit_files(
    workspace_id: str = Path(..., description="Workspace ID"),
    commit_id: str = Path(..., description="提交 ID"),
    service: GitService = Depends(get_git_service),
) -> CommitFilesResponse:
    try:
        return service.get_commit_files(workspace_id, commit_id)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/push",
    response_model=PushResponse,
    summary="推送至遠端",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def push_changes(
    payload: PushRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> PushResponse:
    try:
        return service.push(workspace_id, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/pull",
    response_model=PullResponse,
    summary="拉取遠端更新",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def pull_changes(
    payload: PullRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> PullResponse:
    try:
        return service.pull(workspace_id, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.post(
    "/fetch",
    response_model=FetchResponse,
    summary="同步遠端引用",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def fetch_changes(
    payload: FetchRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> FetchResponse:
    try:
        return service.fetch(workspace_id, payload)
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/diff",
    response_model=DiffResponse,
    summary="取得差異",
    responses=build_responses(401, 404, 422, 500),
)
async def get_diff(
    workspace_id: str = Path(..., description="Workspace ID"),
    path: str = Query(..., description="檔案路徑"),
    base: str | None = Query(None, description="比較基準"),
    head: str | None = Query(None, description="比較目標"),
    context: int = Query(3, ge=0, description="上下文行數"),
    include_metadata: bool = Query(False, alias="includeMetadata", description="是否包含中繼資料"),
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
        )
    except VersionControlError as exc:
        raise _handle_error(exc)


@router.get(
    "/blob",
    response_model=BlobResponse,
    summary="讀取指定版本的檔案內容",
    responses=build_responses(401, 404, 422, 500),
)
async def get_blob(
    workspace_id: str = Path(..., description="Workspace ID"),
    path: str = Query(..., description="檔案路徑"),
    revision: str | None = Query(None, description="提交或引用"),
    service: GitService = Depends(get_git_service),
) -> BlobResponse:
    try:
        return service.blob(workspace_id, path=path, revision=revision)
    except VersionControlError as exc:
        raise _handle_error(exc)


__all__ = ["router"]
