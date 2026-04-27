"""Task API Router.

Provides REST API endpoints for tasks.
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
    """Get Task Service."""
    return TaskService(db)


async def get_execution_service(db: AsyncSession = Depends(get_async_db)) -> ExecutionService:
    """Get Execution Service."""
    return ExecutionService(db)


@router.post(
    "/{session_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create task",
    description="Create a new task in the session.",
)
async def create_task(
    session_id: str,
    data: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Create task.

    Args:
        session_id: Session ID
        data: Creation request
        service: Task Service

    Returns:
        Created task
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
    summary="Get task",
    description="Get task details by ID, supports short ID.",
)
async def get_task(
    session_id: str,
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Get task.

    Args:
        task_id: Task ID
        service: Task Service

    Returns:
        Task data

    Raises:
        HTTPException: Task not found
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
    summary="List tasks",
    description="Query task list for session, supports various filter conditions.",
)
async def list_tasks(
    session_id: str,
    status: Optional[TaskStatus] = Query(None, description="Task status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Offset"),
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """List tasks.

    Args:
        session_id: Session ID
        status: Task status
        limit: Maximum number of records
        offset: Offset
        service: Task Service

    Returns:
        Task list
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
    summary="Stop task",
    description="Request to stop a currently running task.",
)
async def stop_task(
    session_id: str,
    task_id: str,
    service: TaskService = Depends(get_task_service),
    execution_service: ExecutionService = Depends(get_execution_service),
) -> StopTaskResponse:
    """Stop task.

    Args:
        session_id: Session ID
        task_id: Task ID
        service: Task Service
        execution_service: Execution Service

    Returns:
        Stop result

    Raises:
        HTTPException: Task not found or state does not allow stopping
    """
    try:
        # 1. Call execution_service first to actually interrupt SDK
        # This sets stop_requested flag and calls client.interrupt()
        try:
            await execution_service.stop_task(
                session_id=session_id,
                task_id=task_id,
            )
        except Exception as e:
            # Continue updating state even if execution_service fails
            logger.warning("execution_service.stop_task failed: %s", e)

        # 2. Update database state and send WebSocket events
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
