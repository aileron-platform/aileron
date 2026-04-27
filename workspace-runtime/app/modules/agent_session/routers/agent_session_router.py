"""Agent Session API Router.

Provides REST API endpoints for sessions.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.version_control.utils import VersionControlError
from ..domain.enums import AgenticTool, AgentSessionStatus
from ..schemas.agent_session import (
    ToolDecisionRequest,
    ToolDecisionResponse,
    PromptRequest,
    PromptResponse,
    AgentSessionCreate,
    AgentSessionListResponse,
    AgentSessionQuery,
    AgentSessionResponse,
    AgentSessionUpdate,
    ToolResultRequest,
)
from ..services.agent_session_service import AgentSessionService
from ..services.task_service import TaskService
from ..services.tool_decision_service import ToolDecisionService
from ..services.execution_service import ExecutionService
from app.database import async_session_scope, get_async_db

router = APIRouter(prefix="/agent-sessions", tags=["agent-sessions"])


async def get_agent_session_service(db: AsyncSession = Depends(get_async_db)) -> AgentSessionService:
    """Get Session Service."""
    return AgentSessionService(db)


async def get_task_service(db: AsyncSession = Depends(get_async_db)) -> TaskService:
    """Get Task Service."""
    return TaskService(db)


async def get_tool_decision_service(db: AsyncSession = Depends(get_async_db)) -> ToolDecisionService:
    """Get Tool Decision Service."""
    return ToolDecisionService(db)


async def get_execution_service(db: AsyncSession = Depends(get_async_db)) -> ExecutionService:
    """Get Execution Service."""
    return ExecutionService(db)


@router.post(
    "",
    response_model=AgentSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create session",
    description="Create a new AI conversation session, optionally specifying the Agentic Tool to use.",
)
async def create_session(
    data: AgentSessionCreate,
) -> AgentSessionResponse:
    """Create session.

    Args:
        data: Creation request

    Returns:
        Created session
    """
    # Important: create session must have committed before responding successfully.
    # Otherwise frontend sends prompt immediately after receiving 201, new transaction may not see
    # the just-created agent_session, triggering session_id FK violation.
    async with async_session_scope() as db:
        service = AgentSessionService(db)
        try:
            session = await service.create_session(data)
        except VersionControlError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=str(exc),
            ) from exc
    return AgentSessionResponse.from_entity(session)


@router.get(
    "/{session_id}",
    response_model=AgentSessionResponse,
    summary="Get session",
    description="Get session details by ID, supports short ID.",
)
async def get_session(
    session_id: str,
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionResponse:
    """Get session.

    Args:
        session_id: Session ID (supports short ID)
        service: Session Service

    Returns:
        Session data

    Raises:
        HTTPException: Session not found
    """
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return AgentSessionResponse.from_entity(session)


@router.get(
    "",
    response_model=AgentSessionListResponse,
    summary="List sessions",
    description="List sessions with various filter conditions.",
)
async def list_sessions(
    workspace_id: Optional[str] = Query(None, description="Workspace ID"),
    status: Optional[AgentSessionStatus] = Query(None, description="Session status"),
    agentic_tool: Optional[AgenticTool] = Query(None, description="Agentic Tool"),
    source: Optional[str] = Query(None, description="Source filter (user / automation)"),
    archived: bool = Query(False, description="Include archived"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionListResponse:
    """List sessions.

    Args:
        workspace_id: Workspace ID
        status: Session status
        agentic_tool: Agentic Tool
        archived: Include archived
        limit: Max results
        offset: Offset
        service: Session Service

    Returns:
        Session list
    """
    query = AgentSessionQuery(
        workspace_id=workspace_id,
        status=status,
        agentic_tool=agentic_tool,
        source=source,
        archived=archived,
        limit=limit,
        offset=offset,
    )

    sessions, total = await service.find_sessions(query)

    return AgentSessionListResponse(
        items=[AgentSessionResponse.from_entity(s) for s in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{session_id}",
    response_model=AgentSessionResponse,
    summary="Update session",
    description="Update session attributes.",
)
async def update_session(
    session_id: str,
    data: AgentSessionUpdate,
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionResponse:
    """Update session.

    Args:
        session_id: Session ID
        data: Update data
        service: Session Service

    Returns:
        Updated session

    Raises:
        HTTPException: Session not found
    """
    session = await service.update_session(session_id, data)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return AgentSessionResponse.from_entity(session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete session",
    description="Delete session and all related data.",
)
async def delete_session(
    session_id: str,
    service: AgentSessionService = Depends(get_agent_session_service),
) -> None:
    """Delete session.

    Args:
        session_id: Session ID
        service: Session Service

    Raises:
        HTTPException: Session not found
    """
    success = await service.delete_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )


@router.post(
    "/{session_id}/archive",
    response_model=AgentSessionResponse,
    summary="Archive session",
    description="Archive session so it no longer appears in default lists.",
)
async def archive_session(
    session_id: str,
    reason: str = Query("manual", description="Archive reason"),
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionResponse:
    """Archive session.

    Args:
        session_id: Session ID
        reason: Archive reason
        service: Session Service

    Returns:
        Updated session

    Raises:
        HTTPException: Session not found
    """
    session = await service.archive_session(session_id, reason)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return AgentSessionResponse.from_entity(session)


@router.post(
    "/{session_id}/prompt",
    response_model=PromptResponse,
    summary="Execute prompt",
    description="Execute prompt in session, starting the Agentic Tool.",
)
async def execute_prompt(
    session_id: str,
    data: PromptRequest,
    execution_service: ExecutionService = Depends(get_execution_service),
) -> PromptResponse:
    """Execute prompt.

    Uses ExecutionService to coordinate SDK execution, message persistence, and WebSocket streaming.

    Args:
        session_id: Session ID
        data: Prompt request
        execution_service: Execution Service

    Returns:
        Execution status

    Raises:
        HTTPException: Session not found or already running
    """
    from ..services.execution_service import ExecutionServiceError

    try:
        result = await execution_service.execute_prompt(
            session_id=session_id,
            prompt=data.prompt,
            stream=data.stream,
            thinking_mode=data.thinking_mode,
            thinking_budget=data.thinking_budget,
            permission_mode=data.permission_mode.value if data.permission_mode else None,
            images=data.images,
            automation_execution_id=data.automation_execution_id,
        )
        return PromptResponse(
            success=result["success"],
            task_id=result.get("task_id"),
            status=result["status"],
            streaming=result.get("streaming", False),
            queued=result.get("queued"),
            message_id=result.get("message_id"),
            queue_position=result.get("queue_position"),
        )
        
    except ExecutionServiceError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        elif "active task" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )


@router.post(
    "/{session_id}/tool-decision",
    response_model=ToolDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Handle tool decision",
    description="Handle tool execution decisions (permission/user_input).",
)
async def handle_tool_decision(
    session_id: str,
    data: ToolDecisionRequest,
    tool_decision_service: ToolDecisionService = Depends(get_tool_decision_service),
) -> ToolDecisionResponse:
    """Handle tool decision.

    This endpoint handles two tasks:
    1. Wake up waiting decision hooks (if any)
    2. Update decision status in database

    Args:
        session_id: Session ID
        data: Tool Decision request
        tool_decision_service: Tool Decision Service

    Returns:
        Handling result
    """
    from ..services.tool_decision_manager import global_tool_decision_manager

    try:
        decision_dict = data.model_dump(mode="json")

        # Step 1: Try to wake up waiting decision hooks
        hooks_resolved = global_tool_decision_manager.resolve_decision(session_id, decision_dict)

        # Step 2: Update database status (even if hooks not found)
        db_success = await tool_decision_service.resolve_decision(data)

        return ToolDecisionResponse(
            success=hooks_resolved or db_success,
            request_id=data.request_id,
            outcome=data.outcome,
            option_id=data.option_id,
            hooks_resolved=hooks_resolved,
            db_updated=db_success,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{session_id}/tool-result",
    status_code=status.HTTP_200_OK,
    summary="Submit tool result",
    description="Submit results for user interaction tools (e.g., AskUserQuestion).",
)
async def submit_tool_result(
    session_id: str,
    data: ToolResultRequest,
    execution_service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Submit tool result.

    For handling tools that require user interaction, such as AskUserQuestion.
    Send user response as tool_result back to Claude SDK.

    Args:
        session_id: Session ID
        data: Tool result request
        execution_service: Execution Service

    Returns:
        Handling result
    """
    from ..services.tools.claude.claude_tool import ClaudeTool
    from ..services.tool_decision_manager import global_tool_decision_manager

    try:
        # Try to resolve waiting tool input request (if hooks mechanism exists)
        # Currently AskUserQuestion can be handled via a permission-like mechanism
        decision_dict = {
            "request_id": data.tool_use_id,
            "tool_use_id": data.tool_use_id,
            "content": data.content,
            "is_error": data.is_error,
        }

        # Try to resolve via global tool decision manager (may be AskUserQuestion hook)
        hooks_resolved = global_tool_decision_manager.resolve_tool_input(session_id, decision_dict)

        return {
            "success": True,
            "tool_use_id": data.tool_use_id,
            "hooks_resolved": hooks_resolved,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{session_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete queued message",
    description="Delete message from queue. Can only delete messages with queued status.",
)
async def delete_queued_message(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete queued message.

    Args:
        session_id: Session ID
        message_id: Message ID
        db: Database session

    Raises:
        HTTPException: Message not found or not in queued status
    """
    from ..services.message_service import MessageService
    from ..domain.enums import MessageStatus
    from ..websocket.events import get_event_emitter, EventType, WebSocketEvent

    message_service = MessageService(db)
    emitter = get_event_emitter()

    target_message = await message_service.get_message(message_id)
    if not target_message or target_message.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queued message not found: {message_id}",
        )

    if target_message.status == MessageStatus.DISPATCHING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Queued message is already being processed: {message_id}",
        )

    if target_message.status != MessageStatus.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queued message not found: {message_id}",
        )

    # Delete message
    success = await message_service.delete_queued_message(message_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to delete message: {message_id}",
        )

    # Send MESSAGE_DEQUEUED event
    # Note: no need to manually commit, get_async_db already uses session.begin() to manage transaction
    await emitter.emit(
        WebSocketEvent(
            type=EventType.MESSAGE_DEQUEUED,
            session_id=session_id,
            task_id=None,
            data={
                "message_id": message_id,
                "queue_position": target_message.queue_position,
                "reason": "deleted",
            },
        )
    )


@router.get(
    "/{session_id}/queued-messages",
    summary="Get queued messages",
    description="Get all queued messages waiting to be processed in the session.",
)
async def get_queued_messages(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Get queued messages.

    Args:
        session_id: Session ID
        db: Database session

    Returns:
        Queued message list
    """
    from ..services.message_service import MessageService
    from ..services.execution_service import ExecutionService

    message_service = MessageService(db)
    messages = await message_service.get_queued_messages(session_id)

    return {
        "session_id": session_id,
        "count": len(messages),
        "max_queue_size": ExecutionService.MAX_QUEUE_SIZE,
        "messages": [
            {
                "message_id": msg.id,
                "queue_position": msg.queue_position,
                "content_preview": msg.content_preview,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "status": msg.status.value if msg.status else None,
            }
            for msg in messages
        ],
    }


@router.get(
    "/{session_id}/current-execution",
    summary="Get current execution state",
    description="Get current execution state of the session.",
)
async def get_current_execution(
    session_id: str,
    session_service: AgentSessionService = Depends(get_agent_session_service),
) -> dict:
    """Get current execution state.

    Args:
        session_id: Session ID
        session_service: Session Service

    Returns:
        Execution status
    """
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    result = await session_service.get_current_execution(session.workspace_id)
    return result


__all__ = ["router"]
