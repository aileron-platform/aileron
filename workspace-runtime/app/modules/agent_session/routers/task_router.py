"""Task API Router.

提供任務相關的 REST API 端點。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from ..domain.enums import TaskStatus
from ..schemas.task import (
    StopTaskResponse,
    TaskCreate,
    TaskListResponse,
    TaskQuery,
    TaskResponse,
)
from ..services.task_service import (
    InvalidStateTransitionError,
    TaskService,
    TaskServiceError,
)
from ..services.execution_service import ExecutionService

from app.database import get_async_db

router = APIRouter(prefix="/agent-sessions", tags=["agent-session-tasks"])


async def get_task_service(db: AsyncSession = Depends(get_async_db)) -> TaskService:
    """取得 Task Service."""
    return TaskService(db)


async def get_execution_service(db: AsyncSession = Depends(get_async_db)) -> ExecutionService:
    """取得 Execution Service."""
    return ExecutionService(db)


@router.post(
    "/{session_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立任務",
    description="在會話中建立新的任務。",
)
async def create_task(
    session_id: str,
    data: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """建立任務.

    Args:
        session_id: 會話 ID
        data: 建立請求
        service: Task Service

    Returns:
        建立的任務
    """
    task = await service.create_task(
        session_id=session_id,
        full_prompt=data.full_prompt or "",
        created_by=data.created_by,
    )
    return TaskResponse.from_entity(task)


@router.get(
    "/{session_id}/tasks/{task_id}",
    response_model=TaskResponse,
    summary="取得任務",
    description="依 ID 取得任務詳細資料，支援短 ID。",
)
async def get_task(
    session_id: str,
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """取得任務.

    Args:
        task_id: 任務 ID
        service: Task Service

    Returns:
        任務資料

    Raises:
        HTTPException: 任務不存在
    """
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    return TaskResponse.from_entity(task)


@router.get(
    "/{session_id}/tasks",
    response_model=TaskListResponse,
    summary="查詢任務列表",
    description="查詢會話的任務列表，支援多種過濾條件。",
)
async def list_tasks(
    session_id: str,
    status: Optional[TaskStatus] = Query(None, description="任務狀態"),
    limit: int = Query(50, ge=1, le=200, description="最大筆數"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """查詢任務列表.

    Args:
        session_id: 會話 ID
        status: 任務狀態
        limit: 最大筆數
        offset: 偏移量
        service: Task Service

    Returns:
        任務列表
    """
    query = TaskQuery(
        session_id=session_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    tasks, total = await service.find_tasks(query)

    return TaskListResponse(
        items=[TaskResponse.from_entity(t) for t in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{session_id}/tasks/{task_id}/stop",
    response_model=StopTaskResponse,
    summary="停止任務",
    description="請求停止正在執行的任務。",
)
async def stop_task(
    session_id: str,
    task_id: str,
    service: TaskService = Depends(get_task_service),
    execution_service: ExecutionService = Depends(get_execution_service),
) -> StopTaskResponse:
    """停止任務.

    Args:
        session_id: 會話 ID
        task_id: 任務 ID
        service: Task Service
        execution_service: Execution Service

    Returns:
        停止結果

    Raises:
        HTTPException: 任務不存在或狀態不允許停止
    """
    try:
        # 1. 先調用 execution_service 來實際中斷 SDK
        # 這會設定 stop_requested 標記並調用 client.interrupt()
        try:
            await execution_service.stop_task(
                session_id=session_id,
                task_id=task_id,
            )
        except Exception as e:
            # 即使 execution_service 失敗，也繼續更新狀態
            logger.warning("execution_service.stop_task failed: %s", e)

        # 2. 更新數據庫狀態和發送 WebSocket 事件
        task = await service.stop_task(task_id)
        return StopTaskResponse(
            success=True,
            task_id=task.id,
            status=task.status,
        )
    except TaskServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


__all__ = ["router"]
