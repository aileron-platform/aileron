"""Message API Router.

提供訊息相關的 REST API 端點。
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.enums import MessageRole, MessageType
from ..schemas.message import (
    BulkCreateResponse,
    MessageBulkCreate,
    MessageCreate,
    MessageListResponse,
    MessageQuery,
    MessageResponse,
)
from ..services.message_service import MessageService, MessageServiceError

from app.database import get_async_db

router = APIRouter(prefix="/agent-sessions", tags=["agent-session-messages"])


async def get_message_service(db: AsyncSession = Depends(get_async_db)) -> MessageService:
    """取得 Message Service."""
    return MessageService(db)


@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立訊息",
    description="在會話中建立新的訊息。",
)
async def create_message(
    session_id: str,
    data: MessageCreate,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    """建立訊息.

    Args:
        session_id: 會話 ID
        data: 建立請求
        service: Message Service

    Returns:
        建立的訊息
    """
    # 確保 data 中的 session_id 與路徑參數一致
    data.session_id = session_id
    message = await service.create_message(data)
    return MessageResponse.from_entity(message)


@router.get(
    "/{session_id}/messages/{message_id}",
    response_model=MessageResponse,
    summary="取得訊息",
    description="依 ID 取得訊息詳細資料，支援短 ID。",
)
async def get_message(
    session_id: str,
    message_id: str,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    """取得訊息.

    Args:
        message_id: 訊息 ID
        service: Message Service

    Returns:
        訊息資料

    Raises:
        HTTPException: 訊息不存在
    """
    message = await service.get_message(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message not found: {message_id}",
        )
    return MessageResponse.from_entity(message)


@router.get(
    "/{session_id}/messages",
    response_model=MessageListResponse,
    summary="查詢訊息列表",
    description="查詢會話的訊息列表，支援多種過濾條件。",
)
async def list_messages(
    session_id: str,
    task_id: Optional[str] = Query(None, description="任務 ID"),
    type: Optional[MessageType] = Query(None, description="訊息類型"),
    role: Optional[MessageRole] = Query(None, description="訊息角色"),
    limit: int = Query(100, ge=1, le=500, description="最大筆數"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: MessageService = Depends(get_message_service),
) -> MessageListResponse:
    """查詢訊息列表.

    Args:
        session_id: 會話 ID
        task_id: 任務 ID
        type: 訊息類型
        role: 訊息角色
        limit: 最大筆數
        offset: 偏移量
        service: Message Service

    Returns:
        訊息列表
    """
    query = MessageQuery(
        session_id=session_id,
        task_id=task_id,
        type=type,
        role=role,
        limit=limit,
        offset=offset,
    )

    try:
        messages, total = await service.find_messages(query)
    except MessageServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return MessageListResponse(
        items=[MessageResponse.from_entity(m) for m in messages],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/{session_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除訊息",
    description="刪除訊息。",
)
async def delete_message(
    session_id: str,
    message_id: str,
    service: MessageService = Depends(get_message_service),
) -> None:
    """刪除訊息.

    Args:
        message_id: 訊息 ID
        service: Message Service

    Raises:
        HTTPException: 訊息不存在
    """
    success = await service.delete_message(message_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message not found: {message_id}",
        )


@router.post(
    "/{session_id}/messages/bulk",
    response_model=BulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="批次建立訊息",
    description="批次建立多個訊息。",
)
async def create_messages_bulk(
    session_id: str,
    data: MessageBulkCreate,
    service: MessageService = Depends(get_message_service),
) -> BulkCreateResponse:
    """批次建立訊息.

    Args:
        session_id: 會話 ID
        data: 批次建立請求
        service: Message Service

    Returns:
        建立結果
    """
    # 確保所有訊息的 session_id 一致
    for msg in data.messages:
        msg.session_id = session_id
    messages = await service.create_bulk(data.messages)
    return BulkCreateResponse(
        success=True,
        created_count=len(messages),
        messages=[MessageResponse.from_entity(m) for m in messages],
    )


# NOTE: Queue API 已整合至 agent_session_router.py
# - GET /agent-sessions/{session_id}/queued-messages 取得佇列訊息
# - DELETE /agent-sessions/{session_id}/messages/{message_id} 刪除佇列訊息
# - 佇列訊息透過 execute_prompt 自動建立


__all__ = ["router"]
