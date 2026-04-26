"""
Logging configuration module

Provides structured logging configuration with support for different environment outputs
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

from app.config.settings import get_settings

settings = get_settings()


def setup_logging() -> None:
    """Setup application logging configuration"""

    # Logging configuration dictionary
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
            # Application logging
            "app": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "app_file", "error_file"],
                "propagate": False,
            },
            # FastAPI logging
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
            # SQLAlchemy logging
            "sqlalchemy.engine": {
                "level": "WARN" if not settings.DEBUG else "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            # Docker logging
            "docker": {
                "level": "INFO",
                "handlers": ["console", "app_file"],
                "propagate": False,
            },
            # Celery logging
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

    # In production environment, remove file handler (use container logging)
    if settings.is_production:
        for logger_config in logging_config["loggers"].values():
            logger_config["handlers"] = ["console"]
        logging_config["root"]["handlers"] = ["console"]

    # Apply logging configuration
    logging.config.dictConfig(logging_config)

    # Setup root logger
    logger = logging.getLogger("app")
    logger.info(f"Logging system initialized - Level: {settings.LOG_LEVEL}, Environment: {settings.ENV}")


def get_logger(name: str) -> logging.Logger:
    """Get logger with specified name"""
    return logging.getLogger(f"app.{name}")


# Create loggers for different purposes
def get_api_logger() -> logging.Logger:
    """Get API logger"""
    return get_logger("api")


def get_db_logger() -> logging.Logger:
    """Get database logger"""
    return get_logger("database")


def get_docker_logger() -> logging.Logger:
    """Get Docker logger"""
    return get_logger("docker")


def get_celery_logger() -> logging.Logger:
    """Get Celery logger"""
    return get_logger("celery")


def get_auth_logger() -> logging.Logger:
    """Get authentication logger"""
    return get_logger("auth")