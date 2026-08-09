"""Version control router"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from starlette.concurrency import run_in_threadpool

from app.core.openapi import build_responses
from .models import (
    BlobResponse,
    BranchCreateRequest,
    BranchDeleteRequest,
    BranchListResponse,
    BranchMutationResponse,
    BranchPublishRequest,
    BranchRenameRequest,
    BranchSwitchRequest,
    ChangesResponse,
    CloneRepositoryRequest,
    CommitDetailResponse,
    CommitFilesResponse,
    CommitListResponse,
    CommitRequest,
    CommitResponse,
    ConflictPathsRequest,
    DiffResponse,
    DiscardRequest,
    DiscardResponse,
    FetchRequest,
    FetchResponse,
    GitContextListResponse,
    LfsPatternsResponse,
    LfsPatternsUpdateRequest,
    LfsSnapshotConvertRequest,
    LfsSnapshotPreviewRequest,
    LfsSnapshotPreviewResponse,
    NumstatRequest,
    NumstatResponse,
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    RemoteBranchesResponse,
    RemoteRepositoryRequest,
    RemoteSettingsRequest,
    RemoteSettingsResponse,
    RepositoryInitializeRequest,
    RevertCommitRequest,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlOperationStatus,
    VersionControlRepositoryStatus,
    VersionControlStatus,
)
from .dependencies import get_git_service
from .git_operations import GitService, VersionControlError

T = TypeVar("T")

router = APIRouter(
    prefix="/workspaces/{workspace_id}/version-control",
    tags=["Version control"],
)


def _handle_error(exc: VersionControlError) -> HTTPException:
    operation = exc.operation_status
    operation_status = None
    if operation is not None:
        blocking_scope = operation.blocking_scope
        operation_status = {
            "isActive": True,
            "operation": operation.operation_name,
            "actorDisplayName": operation.actor_display_name or None,
            "startedAt": operation.started_at.isoformat(),
            "blockingScope": (
                blocking_scope.value
                if hasattr(blocking_scope, "value")
                else blocking_scope
            ),
            "stale": operation.stale,
            "retryable": operation.retryable,
            "progressCurrent": operation.progress_current,
            "progressTotal": operation.progress_total,
            "phase": operation.phase,
            "cancellable": operation.cancellable,
            "cancelRequested": operation.cancel_requested,
        }
    blocking_scope = exc.blocking_scope
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "errorCode": exc.error_code,
            "messageKey": exc.message_key,
            "blockingScope": (
                blocking_scope.value
                if hasattr(blocking_scope, "value")
                else blocking_scope
            ),
            "operationStatus": operation_status,
            "stale": exc.stale,
            "canForceUnlock": exc.can_force_unlock,
        },
    )


async def _call_service(callback: Callable[[], T]) -> T:
    try:
        return await run_in_threadpool(callback)
    except VersionControlError as exc:
        raise _handle_error(exc) from exc


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
    return await _call_service(lambda: service.list_contexts(workspace_id))


@router.post(
    "/init",
    response_model=VersionControlStatus,
    summary="Initialize Git repository",
    responses=build_responses(401, 404, 409, 500),
)
async def initialize_repository(
    payload: RepositoryInitializeRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> VersionControlStatus:
    return await _call_service(
        lambda: service.initialize_repository(
            workspace_id, default_branch=payload.defaultBranch
        )
    )


@router.post(
    "/clone",
    response_model=VersionControlStatus,
    summary="Clone Git repository",
    responses=build_responses(401, 404, 409, 422, 500),
)
async def clone_repository(
    payload: CloneRepositoryRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> VersionControlStatus:
    return await _call_service(
        lambda: service.clone_repository(
            workspace_id,
            remote_url=payload.remoteUrl,
            branch=payload.branch,
        )
    )


@router.post(
    "/remote-branches",
    response_model=RemoteBranchesResponse,
    summary="List remote repository branches",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def list_remote_repository_branches(
    payload: RemoteRepositoryRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> RemoteBranchesResponse:
    return await _call_service(
        lambda: service.remote_branches(
            workspace_id,
            remote_url=payload.remoteUrl,
        )
    )


@router.get(
    "/repository",
    response_model=VersionControlRepositoryStatus,
    summary="Get Git repository status",
    responses=build_responses(401, 404, 500),
)
async def get_repository_status(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: GitService = Depends(get_git_service),
) -> VersionControlRepositoryStatus:
    return await _call_service(lambda: service.get_repository_status(workspace_id))


@router.get(
    "/status",
    response_model=VersionControlStatus,
    summary="Get Git status",
    responses=build_responses(401, 404, 500),
)
async def get_status(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> VersionControlStatus:
    return await _call_service(lambda: service.get_status(workspace_id, context_id))


@router.get(
    "/operation-status",
    response_model=VersionControlOperationStatus,
    summary="Get current Git operation status",
    responses=build_responses(401, 404, 500),
)
async def get_operation_status(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> VersionControlOperationStatus:
    return service.get_operation_status(workspace_id, context_id)


@router.post(
    "/lfs",
    response_model=BranchMutationResponse,
    summary="Update Git LFS patterns",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def update_lfs_patterns(
    payload: LfsPatternsUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.update_lfs_patterns(
            workspace_id,
            patterns=payload.patterns,
            context_id=context_id,
        )
    )


@router.get(
    "/lfs",
    response_model=LfsPatternsResponse,
    summary="Get Git LFS patterns",
    responses=build_responses(401, 404, 422, 500),
)
async def get_lfs_patterns(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> LfsPatternsResponse:
    return await _call_service(
        lambda: service.get_lfs_patterns(workspace_id, context_id)
    )


@router.post(
    "/lfs/preview",
    response_model=LfsSnapshotPreviewResponse,
    summary="Preview Git LFS snapshot conversion",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def preview_lfs_snapshot(
    payload: LfsSnapshotPreviewRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> LfsSnapshotPreviewResponse:
    return await _call_service(
        lambda: service.preview_lfs_snapshot(
            workspace_id,
            patterns=payload.patterns,
            context_id=context_id,
        )
    )


@router.post(
    "/lfs/convert",
    response_model=BranchMutationResponse,
    summary="Convert files to Git LFS pointers",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def convert_lfs_snapshot(
    payload: LfsSnapshotConvertRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.convert_lfs_snapshot(
            workspace_id,
            paths=payload.paths,
            context_id=context_id,
        )
    )


@router.post(
    "/operation/cancel",
    response_model=BranchMutationResponse,
    summary="Cancel active Git operation",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def cancel_operation(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.cancel_operation(workspace_id, context_id=context_id)
    )


@router.get(
    "/branches",
    response_model=BranchListResponse,
    summary="Get branch list",
    responses=build_responses(401, 404, 422, 500),
)
async def list_branches(
    workspace_id: str = Path(..., description="Workspace ID"),
    include_remote: bool = Query(
        True, alias="includeRemote", description="Whether to include remotes"
    ),
    search: str | None = Query(None, description="Name filter"),
    include_metadata: bool = Query(
        True,
        alias="includeMetadata",
        description="Whether to include branch statistics and last commit info",
    ),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> BranchListResponse:
    return await _call_service(
        lambda: service.list_branches(
            workspace_id,
            include_remote=include_remote,
            search=search,
            context_id=context_id,
            include_metadata=include_metadata,
        )
    )


@router.post(
    "/branches/create",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_branch(
    payload: BranchCreateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.create_branch(
            workspace_id,
            name=payload.name,
            start_point=payload.startPoint,
            upstream=payload.upstream,
            context_id=context_id,
        )
    )


@router.post(
    "/branches/switch",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def switch_branch(
    payload: BranchSwitchRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.switch_branch(
            workspace_id, name=payload.name, context_id=context_id
        )
    )


@router.post(
    "/branches/rename",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def rename_branch(
    payload: BranchRenameRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.rename_branch(
            workspace_id,
            old_name=payload.oldName,
            new_name=payload.newName,
            context_id=context_id,
        )
    )


@router.post(
    "/branches/delete",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def delete_branch(
    payload: BranchDeleteRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.delete_branch(
            workspace_id, name=payload.name, context_id=context_id
        )
    )


@router.post(
    "/branches/publish",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def publish_branch(
    payload: BranchPublishRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.publish_branch(
            workspace_id,
            remote=payload.remote,
            remote_name=payload.remoteName,
            context_id=context_id,
        )
    )


@router.post(
    "/conflicts/mark-resolved",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def mark_conflicts_resolved(
    payload: ConflictPathsRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.mark_conflicts_resolved(
            workspace_id, paths=payload.paths, context_id=context_id
        )
    )


@router.post(
    "/conflicts/abort",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def abort_conflict(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.abort_conflict(workspace_id, context_id=context_id)
    )


@router.post(
    "/commits/revert",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def revert_commit(
    payload: RevertCommitRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(None, alias="contextId"),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.revert_commit(
            workspace_id, sha=payload.sha, context_id=context_id
        )
    )


@router.get(
    "/changes",
    response_model=ChangesResponse,
    summary="Get change list",
    responses=build_responses(401, 404, 422, 500),
)
async def get_changes(
    workspace_id: str = Path(..., description="Workspace ID"),
    group: str = Query("all", pattern="^(all|staged|unstaged|untracked|conflicts)$"),
    cursor: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    include_stats: bool = Query(
        True,
        alias="includeStats",
        description="When false, additions/deletions are null (deferred to /changes/numstat)",
    ),
    service: GitService = Depends(get_git_service),
) -> ChangesResponse:
    return await _call_service(
        lambda: service.get_changes(
            workspace_id,
            group=group,
            cursor=cursor,
            limit=limit,
            context_id=context_id,
            include_stats=include_stats,
        )
    )


@router.post(
    "/changes/numstat",
    response_model=NumstatResponse,
    summary="Get deferred numstat for visible paths",
    responses=build_responses(401, 404, 422, 500),
)
async def get_changes_numstat(
    payload: NumstatRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> NumstatResponse:
    stats = await _call_service(
        lambda: service.get_numstat(
            workspace_id,
            staged_paths=payload.stagedPaths,
            unstaged_paths=payload.unstagedPaths,
            context_id=context_id,
        )
    )
    return NumstatResponse(stats=stats)


@router.post(
    "/stage",
    response_model=StageResponse,
    summary="Stage files",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def stage_changes(
    payload: StageRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> StageResponse:
    return await _call_service(lambda: service.stage(workspace_id, payload, context_id))


@router.post(
    "/unstage",
    response_model=UnstageResponse,
    summary="Unstage files",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def unstage_changes(
    payload: UnstageRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> UnstageResponse:
    return await _call_service(
        lambda: service.unstage(workspace_id, payload, context_id)
    )


@router.post(
    "/discard",
    response_model=DiscardResponse,
    summary="Discard unstaged changes",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def discard_changes(
    payload: DiscardRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> DiscardResponse:
    return await _call_service(
        lambda: service.discard(workspace_id, payload, context_id)
    )


@router.post(
    "/commit",
    response_model=CommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create commit",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_commit(
    payload: CommitRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> CommitResponse:
    return await _call_service(
        lambda: service.commit(workspace_id, payload, context_id)
    )


@router.get(
    "/commits",
    response_model=CommitListResponse,
    summary="List commit history",
    responses=build_responses(401, 404, 422, 500),
)
async def list_commits(
    workspace_id: str = Path(..., description="Workspace ID"),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    query_scope: str = Query(
        "current", alias="queryScope", pattern="^(current|all|local|remote)$"
    ),
    branch: str | None = Query(None, description="Branch name"),
    search: str | None = Query(None, description="Search keyword"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> CommitListResponse:
    return await _call_service(
        lambda: service.list_commits(
            workspace_id,
            cursor=cursor,
            limit=limit,
            query_scope=query_scope,
            branch=branch,
            search=search,
            context_id=context_id,
        )
    )


@router.get(
    "/commits/{commit_id}",
    response_model=CommitDetailResponse,
    summary="Get commit details",
    responses=build_responses(401, 404, 500),
)
async def get_commit(
    workspace_id: str = Path(..., description="Workspace ID"),
    commit_id: str = Path(..., description="Commit ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> CommitDetailResponse:
    return await _call_service(
        lambda: service.get_commit(workspace_id, commit_id, context_id)
    )


@router.get(
    "/commits/{commit_id}/files",
    response_model=CommitFilesResponse,
    summary="Get commit file differences",
    responses=build_responses(401, 404, 500),
)
async def get_commit_files(
    workspace_id: str = Path(..., description="Workspace ID"),
    commit_id: str = Path(..., description="Commit ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> CommitFilesResponse:
    return await _call_service(
        lambda: service.get_commit_files(workspace_id, commit_id, context_id)
    )


@router.post(
    "/push",
    response_model=PushResponse,
    summary="Push to remote",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def push_changes(
    payload: PushRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> PushResponse:
    return await _call_service(lambda: service.push(workspace_id, payload, context_id))


@router.post(
    "/pull",
    response_model=PullResponse,
    summary="Pull remote updates",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def pull_changes(
    payload: PullRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> PullResponse:
    return await _call_service(lambda: service.pull(workspace_id, payload, context_id))


@router.post(
    "/fetch",
    response_model=FetchResponse,
    summary="Sync remote references",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def fetch_changes(
    payload: FetchRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> FetchResponse:
    return await _call_service(lambda: service.fetch(workspace_id, payload, context_id))


@router.get(
    "/remote",
    response_model=RemoteSettingsResponse,
    summary="Get remote settings",
    responses=build_responses(401, 404, 500),
)
async def get_remote_settings(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> RemoteSettingsResponse:
    return await _call_service(
        lambda: service.get_remote_settings(workspace_id, context_id)
    )


@router.put(
    "/remote",
    response_model=BranchMutationResponse,
    summary="Set remote settings",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def set_remote_settings(
    payload: RemoteSettingsRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.set_remote_settings(workspace_id, payload, context_id)
    )


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
    include_metadata: bool = Query(
        False, alias="includeMetadata", description="Whether to include metadata"
    ),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> DiffResponse:
    return await _call_service(
        lambda: service.diff(
            workspace_id,
            path=path,
            base=base,
            head=head,
            context=context,
            include_metadata=include_metadata,
            context_id=context_id,
        )
    )


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
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> BlobResponse:
    return await _call_service(
        lambda: service.blob(
            workspace_id, path=path, revision=revision, context_id=context_id
        )
    )


@router.post(
    "/force-unlock",
    response_model=BranchMutationResponse,
    summary="Force-clear stale git locks",
    responses=build_responses(400, 401, 404, 422, 409, 500),
)
async def force_unlock(
    workspace_id: str = Path(..., description="Workspace ID"),
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
    service: GitService = Depends(get_git_service),
) -> BranchMutationResponse:
    return await _call_service(
        lambda: service.force_unlock(workspace_id=workspace_id, context_id=context_id)
    )


__all__ = ["router"]
