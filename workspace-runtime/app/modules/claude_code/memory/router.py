"""Claude Code Memory 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.core.openapi import build_responses
from .dependencies import get_memory_service
from .models import (
    MemoryCollectionResponse,
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryDocumentResponse,
    MemoryUpdateRequest,
)
from .service import MemoryService

router = APIRouter(prefix="/memory", tags=["Claude Code - Memory"])


@router.get(
    "",
    response_model=MemoryCollectionResponse,
    summary="列出所有 Memory 檔案",
    responses=build_responses(400, 401, 404, 500),
)
async def list_memory_documents(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryCollectionResponse:
    return service.list_documents(workspace_id)


@router.get(
    "/{file_name}",
    response_model=MemoryDocumentResponse,
    summary="取得單一 Memory 檔案",
    responses=build_responses(400, 401, 404, 500),
)
async def get_memory_document(
    workspace_id: str = Path(..., description="Workspace ID"),
    file_name: str = Path(..., description="檔案名稱"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDocumentResponse:
    return service.get_document(workspace_id, file_name)


@router.post(
    "",
    response_model=MemoryDocumentResponse,
    summary="建立 Memory 檔案",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_memory_document(
    payload: MemoryCreateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDocumentResponse:
    return service.create_document(workspace_id, payload)


@router.put(
    "/{file_name}",
    response_model=MemoryDocumentResponse,
    summary="更新 Memory 檔案",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def update_memory_document(
    payload: MemoryUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    file_name: str = Path(..., description="檔案名稱"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDocumentResponse:
    return service.update_document(workspace_id, file_name, payload)


@router.delete(
    "/{file_name}",
    response_model=MemoryDeleteResponse,
    summary="刪除 Memory 檔案",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_memory_document(
    workspace_id: str = Path(..., description="Workspace ID"),
    file_name: str = Path(..., description="檔案名稱"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDeleteResponse:
    return service.delete_document(workspace_id, file_name)
