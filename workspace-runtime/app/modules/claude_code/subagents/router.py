"""Subagents 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from ..common import DocumentScope, check_scope_writable
from .dependencies import get_subagent_service
from .models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDeleteResponse,
    SubagentDocumentResponse,
    SubagentScopeResponse,
    SubagentUpdateRequest,
)
from .service import SubagentService

router = APIRouter(prefix="/subagents", tags=["Claude Code - 子代理"])


def _validate_subagent_scope(scope: DocumentScope, *, check_writable: bool = False) -> None:
    """驗證 Subagents scope

    Args:
        scope: 要驗證的範圍
        check_writable: 是否檢查可寫入性（用於 POST/PUT/DELETE 操作）
    """
    if scope == DocumentScope.LOCAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCOPE", "message": "Subagents 不支援 LOCAL scope"},
        )

    if check_writable:
        try:
            check_scope_writable(scope)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "SCOPE_READ_ONLY", "message": str(e)},
            ) from e


@router.get(
    "",
    response_model=SubagentCollectionResponse,
    summary="列出所有 Subagents",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_subagents(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="可選擇僅回傳指定範圍"
    ),
    service: SubagentService = Depends(get_subagent_service),
) -> SubagentCollectionResponse:
    return service.list_scopes(workspace_id, scope)


@router.get(
    "/{scope}",
    response_model=SubagentScopeResponse,
    summary="取得指定範圍 Subagents",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope_subagents(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Subagent 範圍"),
    service: SubagentService = Depends(get_subagent_service),
) -> SubagentScopeResponse:
    _validate_subagent_scope(scope, check_writable=False)
    return service.get_scope(workspace_id, scope)


@router.get(
    "/{scope}/{file_name}",
    response_model=SubagentDocumentResponse,
    summary="取得 Subagent 內容",
    responses=build_responses(400, 401, 404, 500),
)
async def get_subagent(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Subagent 範圍"),
    file_name: str = Path(..., description="檔案名稱"),
    service: SubagentService = Depends(get_subagent_service),
) -> SubagentDocumentResponse:
    _validate_subagent_scope(scope, check_writable=False)
    return service.get_document(workspace_id, scope, file_name)


@router.post(
    "/{scope}",
    response_model=SubagentDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增 Subagent",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def create_subagent(
    payload: SubagentCreateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Subagent 範圍"),
    service: SubagentService = Depends(get_subagent_service),
) -> SubagentDocumentResponse:
    _validate_subagent_scope(scope, check_writable=True)
    return service.create_document(workspace_id, scope, payload)


@router.put(
    "/{scope}/{file_name}",
    response_model=SubagentDocumentResponse,
    summary="更新 Subagent",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def update_subagent(
    payload: SubagentUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Subagent 範圍"),
    file_name: str = Path(..., description="檔案名稱"),
    service: SubagentService = Depends(get_subagent_service),
) -> SubagentDocumentResponse:
    _validate_subagent_scope(scope, check_writable=True)
    return service.update_document(workspace_id, scope, file_name, payload)


@router.delete(
    "/{scope}/{file_name}",
    response_model=SubagentDeleteResponse,
    summary="刪除 Subagent",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_subagent(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Subagent 範圍"),
    file_name: str = Path(..., description="檔案名稱"),
    service: SubagentService = Depends(get_subagent_service),
) -> SubagentDeleteResponse:
    _validate_subagent_scope(scope, check_writable=True)
    service.delete_document(workspace_id, scope, file_name)
    return SubagentDeleteResponse(
        workspaceId=workspace_id,
        scope=scope,
        fileName=file_name,
        deleted=True,
    )
