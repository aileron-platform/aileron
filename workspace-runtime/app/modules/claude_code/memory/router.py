"""Claude Code Memory Routes"""

from __future__ import annotations

from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error
from ..documents import DocumentScope, check_scope_writable
from .dependencies import get_memory_service
from .models import (
    MemoryCollectionResponse,
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryDocumentResponse,
    MemoryUpdateRequest,
)
from .documents import MemoryService

router = APIRouter(prefix="/memory", tags=["Claude Code - Memory"])

T = TypeVar("T")


def _call_service(operation: Callable[[], T]) -> T:
    return operation()


def _validate_memory_scope(
    scope: DocumentScope, *, check_writable: bool = False
) -> None:
    if scope in (DocumentScope.LOCAL, DocumentScope.PLUGIN):
        raise_resource_error(
            "INVALID_SCOPE",
            f"Memory does not support {scope.value} scope",
            status.HTTP_400_BAD_REQUEST,
        )
    if check_writable:
        try:
            check_scope_writable(scope)
        except ValueError as error:
            raise_resource_error(
                "SCOPE_READ_ONLY", str(error), status.HTTP_403_FORBIDDEN
            )


@router.get(
    "",
    response_model=MemoryCollectionResponse,
    summary="List all memory files",
    responses=build_responses(400, 401, 404, 500),
)
async def list_memory_documents(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryCollectionResponse:
    return _call_service(lambda: service.list_documents(workspace_id))


@router.get(
    "/{scope}/content",
    response_model=MemoryDocumentResponse,
    summary="Get single memory file",
    responses=build_responses(400, 401, 404, 500),
)
async def get_memory_document(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Memory scope"),
    path: str = Query(..., description="File path"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDocumentResponse:
    _validate_memory_scope(scope)
    return _call_service(lambda: service.get_document(workspace_id, scope, path))


@router.post(
    "/{scope}",
    response_model=MemoryDocumentResponse,
    summary="Create memory file",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_memory_document(
    payload: MemoryCreateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Memory scope"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDocumentResponse:
    _validate_memory_scope(scope, check_writable=True)
    return _call_service(lambda: service.create_document(workspace_id, scope, payload))


@router.put(
    "/{scope}/content",
    response_model=MemoryDocumentResponse,
    summary="Update memory file",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def update_memory_document(
    payload: MemoryUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Memory scope"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDocumentResponse:
    _validate_memory_scope(scope, check_writable=True)
    return _call_service(lambda: service.update_document(workspace_id, scope, payload))


@router.delete(
    "/{scope}/content",
    response_model=MemoryDeleteResponse,
    summary="Delete memory file",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_memory_document(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Memory scope"),
    path: str = Query(..., description="File path"),
    revision: str = Query(..., description="Expected document revision token"),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryDeleteResponse:
    _validate_memory_scope(scope, check_writable=True)
    return _call_service(
        lambda: service.delete_document(workspace_id, scope, path, revision)
    )
