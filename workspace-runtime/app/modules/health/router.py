"""健康檢查路由"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.utils.datetime_utils import utcnow

from .service import HealthCheckService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["健康檢查"])


@router.get("", summary="服務健康檢查")
async def health_check(db: Session = Depends(get_db)) -> dict[str, object]:
    """
    提供運行時服務的健康狀態

    同時檢查並更新資料庫中的以下欄位：
    - runtime_status: 確保為 'running'
    - runtime_container_id: 更新為當前容器 ID
    - runtime_last_seen: 更新為當前時間
    """
    logger.debug("Health check called")
    try:
        service = HealthCheckService(db)
        result = service.check_and_update_workspace_status()
        logger.debug("Health check result: %s", result.get('status'))
        return result
    except Exception as e:
        # 如果資料庫連線失敗，仍然返回基本的健康狀態
        settings = get_settings()
        return {
            "status": "degraded",
            "service": "workspace-runtime",
            "workspace_id": settings.WORKSPACE_ID,
            "error": f"Database connection failed: {str(e)}",
            "timestamp": utcnow().isoformat() + "Z",
        }
