"""Message API Router.

Provides REST API endpoints for messages.
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
    """Get Message Service."""
    return MessageService(db)


@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create message",
    description="Create a new message in the session.",
)
async def create_message(
    session_id: str,
    data: MessageCreate,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    """Create message.

    Args:
        session_id: Session ID
        data: Creation request
        service: Message Service

    Returns:
        Created message
    """
    # Ensure session_id in data matches path parameter
    data.session_id = session_id
    message = await service.create_message(data)
    return MessageResponse.from_entity(message)


@router.get(
    "/{session_id}/messages/{message_id}",
    response_model=MessageResponse,
    summary="Get message",
    description="Get message details by ID, supports short ID.",
)
async def get_message(
    session_id: str,
    message_id: str,
    service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    """Get message.

    Args:
        message_id: Message ID
        service: Message Service

    Returns:
        Message data

    Raises:
        HTTPException: Message not found
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
    summary="List messages",
    description="Query message list for session, supports various filter conditions.",
)
async def list_messages(
    session_id: str,
    task_id: Optional[str] = Query(None, description="Task ID"),
    type: Optional[MessageType] = Query(None, description="Message type"),
    role: Optional[MessageRole] = Query(None, description="Message role"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Offset"),
    service: MessageService = Depends(get_message_service),
) -> MessageListResponse:
    """List messages.

    Args:
        session_id: Session ID
        task_id: Task ID
        type: Message type
        role: Message role
        limit: Maximum number of records
        offset: Offset
        service: Message Service

    Returns:
        Message list
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
    summary="Delete message",
    description="Delete message.",
)
async def delete_message(
    session_id: str,
    message_id: str,
    service: MessageService = Depends(get_message_service),
) -> None:
    """Delete message.

    Args:
        message_id: Message ID
        service: Message Service

    Raises:
        HTTPException: Message not found
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
    summary="Bulk create messages",
    description="Create multiple messages in bulk.",
)
async def create_messages_bulk(
    session_id: str,
    data: MessageBulkCreate,
    service: MessageService = Depends(get_message_service),
) -> BulkCreateResponse:
    """Bulk create messages.

    Args:
        session_id: Session ID
        data: Bulk creation request
        service: Message Service

    Returns:
        Creation result
    """
    # Ensure all messages have consistent session_id
    for msg in data.messages:
        msg.session_id = session_id
    messages = await service.create_bulk(data.messages)
    return BulkCreateResponse(
        success=True,
        created_count=len(messages),
        messages=[MessageResponse.from_entity(m) for m in messages],
    )


# NOTE: Queue API has been integrated into agent_session_router.py
# - GET /agent-sessions/{session_id}/queued-messages get queued messages
# - DELETE /agent-sessions/{session_id}/messages/{message_id} delete queued message
# - Queued messages are automatically created via execute_prompt


__all__ = ["router"]
