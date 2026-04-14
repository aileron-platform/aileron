"""任務進度追蹤服務"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任務狀態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskProgress:
    """任務進度信息"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0  # 0-100
    message: str = ""
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """轉換為字典"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
        }


class TaskProgressService:
    """任務進度管理服務"""

    def __init__(self):
        self._tasks: Dict[str, TaskProgress] = {}

    def create_task(self, task_type: str = "default") -> str:
        """建立新任務並返回任務 ID"""
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = TaskProgress(task_id=task_id)
        logger.info(f"建立任務: {task_id}")
        return task_id

    def get_progress(self, task_id: str) -> Optional[TaskProgress]:
        """取得任務進度"""
        return self._tasks.get(task_id)

    def update_progress(
        self,
        task_id: str,
        progress: int,
        message: str = "",
        status: Optional[TaskStatus] = None,
    ) -> bool:
        """更新任務進度"""
        if task_id not in self._tasks:
            logger.warning(f"任務不存在: {task_id}")
            return False

        task = self._tasks[task_id]
        task.progress = min(100, max(0, progress))
        task.message = message

        if status:
            task.status = status
            if status == TaskStatus.RUNNING and not task.started_at:
                task.started_at = datetime.utcnow()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                task.completed_at = datetime.utcnow()

        logger.debug(f"更新任務進度: {task_id} - {task.progress}%")
        return True

    def set_error(self, task_id: str, error: str) -> bool:
        """設定任務錯誤"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.error = error
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        logger.error(f"任務失敗: {task_id} - {error}")
        return True

    def set_completed(self, task_id: str, result: Optional[Dict] = None) -> bool:
        """標記任務為完成"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.completed_at = datetime.utcnow()
        task.result = result
        logger.info(f"任務完成: {task_id}")
        return True

    def cleanup_old_tasks(self, max_age_seconds: int = 3600) -> int:
        """清理舊任務（預設 1 小時）"""
        now = datetime.utcnow()
        to_delete = []

        for task_id, task in self._tasks.items():
            if task.completed_at:
                age = (now - task.completed_at).total_seconds()
                if age > max_age_seconds:
                    to_delete.append(task_id)

        for task_id in to_delete:
            del self._tasks[task_id]

        if to_delete:
            logger.info(f"清理了 {len(to_delete)} 個舊任務")

        return len(to_delete)


# 全局任務進度服務實例
_task_progress_service: Optional[TaskProgressService] = None


def get_task_progress_service() -> TaskProgressService:
    """取得全局任務進度服務實例"""
    global _task_progress_service
    if _task_progress_service is None:
        _task_progress_service = TaskProgressService()
    return _task_progress_service


__all__ = [
    "TaskStatus",
    "TaskProgress",
    "TaskProgressService",
    "get_task_progress_service",
]

