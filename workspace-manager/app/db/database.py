"""資料庫連線和配置"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _create_engine() -> Engine:
    """建立資料庫引擎，針對 SQLite 進行特殊處理"""

    database_url = settings.DATABASE_URL
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False},
        )

    return create_engine(
        database_url,
        echo=settings.DEBUG,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


# 創建資料庫引擎
engine = _create_engine()

# 創建 Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 創建 Base
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """獲取資料庫 session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """創建資料庫表"""
    from app.db import models  # noqa: F401 - 確保模型已載入

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("資料庫表創建成功")
    except Exception as exc:  # pragma: no cover - 真實錯誤需向外拋出
        logger.error("資料庫表創建失敗: %s", exc)
        raise
