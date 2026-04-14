"""健康檢查依賴注入"""

from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from app.database.session import get_db

from .service import HealthCheckService


def get_health_check_service(db: Session = None) -> Generator[HealthCheckService, None, None]:
    """獲取健康檢查服務實例"""
    if db is None:
        from app.database.session import get_session_local
        session_local = get_session_local()
        db = session_local()
        try:
            yield HealthCheckService(db)
        finally:
            db.close()
    else:
        yield HealthCheckService(db)


__all__ = ["get_health_check_service"]

