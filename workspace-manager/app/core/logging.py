"""
日誌配置模組

提供結構化日誌配置，支援不同環境的日誌輸出
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

from app.config.settings import get_settings

settings = get_settings()


def setup_logging() -> None:
    """設定應用程式日誌配置"""

    # 日誌配置字典
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}',
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "detailed" if settings.DEBUG else "default",
                "stream": sys.stdout,
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "logs/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "detailed",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 3,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            # 應用程式日誌
            "app": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "app_file", "error_file"],
                "propagate": False,
            },
            # FastAPI 日誌
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            # SQLAlchemy 日誌
            "sqlalchemy.engine": {
                "level": "WARN" if not settings.DEBUG else "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            # Docker 日誌
            "docker": {
                "level": "INFO",
                "handlers": ["console", "app_file"],
                "propagate": False,
            },
            # Celery 日誌
            "celery": {
                "level": "INFO",
                "handlers": ["console", "app_file"],
                "propagate": False,
            },
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console"],
        },
    }

    # 在生產環境中，移除檔案處理器（使用容器日誌）
    if settings.is_production:
        for logger_config in logging_config["loggers"].values():
            logger_config["handlers"] = ["console"]
        logging_config["root"]["handlers"] = ["console"]

    # 套用日誌配置
    logging.config.dictConfig(logging_config)

    # 設定根日誌記錄器
    logger = logging.getLogger("app")
    logger.info(f"日誌系統已初始化 - 等級: {settings.LOG_LEVEL}, 環境: {settings.ENV}")


def get_logger(name: str) -> logging.Logger:
    """取得指定名稱的日誌記錄器"""
    return logging.getLogger(f"app.{name}")


# 建立不同用途的日誌記錄器
def get_api_logger() -> logging.Logger:
    """取得 API 日誌記錄器"""
    return get_logger("api")


def get_db_logger() -> logging.Logger:
    """取得資料庫日誌記錄器"""
    return get_logger("database")


def get_docker_logger() -> logging.Logger:
    """取得 Docker 日誌記錄器"""
    return get_logger("docker")


def get_celery_logger() -> logging.Logger:
    """取得 Celery 日誌記錄器"""
    return get_logger("celery")


def get_auth_logger() -> logging.Logger:
    """取得認證日誌記錄器"""
    return get_logger("auth")