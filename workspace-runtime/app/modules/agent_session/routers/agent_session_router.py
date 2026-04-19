"""Agent Session API Router.

提供會話相關的 REST API 端點。
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
    """取得 Session Service."""
    return AgentSessionService(db)


async def get_task_service(db: AsyncSession = Depends(get_async_db)) -> TaskService:
    """取得 Task Service."""
    return TaskService(db)


async def get_tool_decision_service(db: AsyncSession = Depends(get_async_db)) -> ToolDecisionService:
    """取得 Tool Decision Service."""
    return ToolDecisionService(db)


async def get_execution_service(db: AsyncSession = Depends(get_async_db)) -> ExecutionService:
    """取得 Execution Service."""
    return ExecutionService(db)


@router.post(
    "",
    response_model=AgentSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立會話",
    description="建立新的 AI 對話會話，可指定使用的 Agentic Tool。",
)
async def create_session(
    data: AgentSessionCreate,
) -> AgentSessionResponse:
    """建立會話.

    Args:
        data: 建立請求

    Returns:
        建立的會話
    """
    # 重要：create session 回應成功前必須已 commit。
    # 否則前端在收到 201 後立刻送 prompt，新的 transaction 可能還看不到
    # 剛建立的 agent_session，進而觸發 session_id FK violation。
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
    summary="取得會話",
    description="依 ID 取得會話詳細資料，支援短 ID。",
)
async def get_session(
    session_id: str,
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionResponse:
    """取得會話.

    Args:
        session_id: 會話 ID (支援短 ID)
        service: Session Service

    Returns:
        會話資料

    Raises:
        HTTPException: 會話不存在
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
    summary="查詢會話列表",
    description="查詢會話列表，支援多種過濾條件。",
)
async def list_sessions(
    workspace_id: Optional[str] = Query(None, description="工作區 ID"),
    status: Optional[AgentSessionStatus] = Query(None, description="會話狀態"),
    agentic_tool: Optional[AgenticTool] = Query(None, description="Agentic Tool"),
    source: Optional[str] = Query(None, description="來源過濾 (user / automation)"),
    archived: bool = Query(False, description="是否包含已封存"),
    limit: int = Query(50, ge=1, le=200, description="最大筆數"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionListResponse:
    """查詢會話列表.

    Args:
        workspace_id: 工作區 ID
        status: 會話狀態
        agentic_tool: Agentic Tool
        archived: 是否包含已封存
        limit: 最大筆數
        offset: 偏移量
        service: Session Service

    Returns:
        會話列表
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
    summary="更新會話",
    description="更新會話屬性。",
)
async def update_session(
    session_id: str,
    data: AgentSessionUpdate,
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionResponse:
    """更新會話.

    Args:
        session_id: 會話 ID
        data: 更新資料
        service: Session Service

    Returns:
        更新後的會話

    Raises:
        HTTPException: 會話不存在
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
    summary="刪除會話",
    description="刪除會話及其所有相關資料。",
)
async def delete_session(
    session_id: str,
    service: AgentSessionService = Depends(get_agent_session_service),
) -> None:
    """刪除會話.

    Args:
        session_id: 會話 ID
        service: Session Service

    Raises:
        HTTPException: 會話不存在
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
    summary="封存會話",
    description="封存會話，使其不再出現在預設列表中。",
)
async def archive_session(
    session_id: str,
    reason: str = Query("manual", description="封存原因"),
    service: AgentSessionService = Depends(get_agent_session_service),
) -> AgentSessionResponse:
    """封存會話.

    Args:
        session_id: 會話 ID
        reason: 封存原因
        service: Session Service

    Returns:
        更新後的會話

    Raises:
        HTTPException: 會話不存在
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
    summary="執行 Prompt",
    description="在會話中執行 prompt，啟動 Agentic Tool。",
)
async def execute_prompt(
    session_id: str,
    data: PromptRequest,
    execution_service: ExecutionService = Depends(get_execution_service),
) -> PromptResponse:
    """執行 Prompt.

    使用 ExecutionService 協調 SDK 執行、訊息持久化和 WebSocket 串流。

    Args:
        session_id: 會話 ID
        data: Prompt 請求
        execution_service: Execution Service

    Returns:
        執行狀態

    Raises:
        HTTPException: 會話不存在或正在執行中
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
    summary="處理 Tool Decision",
    description="處理工具執行的決策（permission/user_input）。",
)
async def handle_tool_decision(
    session_id: str,
    data: ToolDecisionRequest,
    tool_decision_service: ToolDecisionService = Depends(get_tool_decision_service),
) -> ToolDecisionResponse:
    """處理 Tool Decision.

    這個 endpoint 處理兩個任務：
    1. 喚醒等待中的決策 hooks（若存在）
    2. 更新資料庫中的決策狀態

    Args:
        session_id: 會話 ID
        data: Tool Decision 請求
        tool_decision_service: Tool Decision Service

    Returns:
        處理結果
    """
    from ..services.tool_decision_manager import global_tool_decision_manager

    try:
        decision_dict = data.model_dump(mode="json")

        # Step 1: 嘗試喚醒等待中的決策 hooks
        hooks_resolved = global_tool_decision_manager.resolve_decision(session_id, decision_dict)

        # Step 2: 更新資料庫狀態（即使 hooks 沒有找到也要更新）
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
    summary="提交工具結果",
    description="提交使用者互動工具（如 AskUserQuestion）的結果。",
)
async def submit_tool_result(
    session_id: str,
    data: ToolResultRequest,
    execution_service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """提交工具結果.

    用於處理需要使用者互動的工具，如 AskUserQuestion。
    將使用者的回應作為 tool_result 發送回 Claude SDK。

    Args:
        session_id: 會話 ID
        data: 工具結果請求
        execution_service: Execution Service

    Returns:
        處理結果
    """
    from ..services.tools.claude.claude_tool import ClaudeTool
    from ..services.tool_decision_manager import global_tool_decision_manager

    try:
        # 嘗試解決等待中的工具輸入請求（如果有 hooks 機制）
        # 目前 AskUserQuestion 可以透過類似 permission 的機制處理
        decision_dict = {
            "request_id": data.tool_use_id,
            "tool_use_id": data.tool_use_id,
            "content": data.content,
            "is_error": data.is_error,
        }

        # 嘗試透過全域 tool decision manager 解決（可能是 AskUserQuestion hook）
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
    summary="刪除佇列訊息",
    description="刪除佇列中的訊息。只能刪除狀態為 queued 的訊息。",
)
async def delete_queued_message(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """刪除佇列訊息.

    Args:
        session_id: 會話 ID
        message_id: 訊息 ID
        db: 資料庫 session

    Raises:
        HTTPException: 訊息不存在或非 queued 狀態
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

    # 刪除訊息
    success = await message_service.delete_queued_message(message_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to delete message: {message_id}",
        )

    # 發送 MESSAGE_DEQUEUED 事件
    # 注意：不需手動 commit，get_async_db 已用 session.begin() 自動管理交易
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
    summary="取得佇列訊息",
    description="取得會話中所有等待處理的佇列訊息。",
)
async def get_queued_messages(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """取得佇列訊息.

    Args:
        session_id: 會話 ID
        db: 資料庫 session

    Returns:
        佇列訊息列表
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
    summary="取得當前執行狀態",
    description="取得會話當前的執行狀態。",
)
async def get_current_execution(
    session_id: str,
    session_service: AgentSessionService = Depends(get_agent_session_service),
) -> dict:
    """取得當前執行狀態.

    Args:
        session_id: 會話 ID
        session_service: Session Service

    Returns:
        執行狀態
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
