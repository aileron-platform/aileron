"""Logging configuration module

Provides unified logging configuration with support for:
- Structured logging (JSON format, suitable for production)
- Console logging (human-readable format, suitable for development)
- Log level control
- Third-party library log filtering
"""

import logging
import sys
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """Structured log formatter (JSON format)"""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "thread_id"):
            log_data["thread_id"] = record.thread_id

        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add source location
        if record.levelno >= logging.WARNING:
            log_data["location"] = f"{record.filename}:{record.lineno}"

        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Console log formatter (human-readable format)"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        # Basic format
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        name = record.name[-30:] if len(record.name) > 30 else record.name

        # Build message
        message = record.getMessage()

        # Add colors
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            level = f"{color}{level}{self.RESET}"

        # Add context
        context_parts = []
        if hasattr(record, "request_id"):
            context_parts.append(f"req={record.request_id[:8]}")
        if hasattr(record, "thread_id"):
            context_parts.append(f"thread={record.thread_id[:8]}")

        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        formatted = f"{timestamp} | {level} | {name}{context} | {message}"

        # Add exception info
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def setup_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """Setup logging configuration

    Args:
        config: Configuration dictionary with the following options:
            - log_level: Log level (DEBUG, INFO, WARNING, ERROR)
            - log_format: Log format ("json" or "console")
            - use_colors: Whether to use colors (console format only)
    """
    config = config or {}

    log_level = config.get("log_level", "INFO")
    log_format = config.get("log_format", "console")
    use_colors = config.get("use_colors", True)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Choose formatter
    if log_format.lower() == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(ConsoleFormatter(use_colors=use_colors))

    root_logger.addHandler(handler)

    # Configure third-party library log levels
    _configure_third_party_loggers(log_level)

    logging.info(f"Logging configured: level={log_level}, format={log_format}")


def _configure_third_party_loggers(app_log_level: str) -> None:
    """Configure third-party library log levels"""
    # Reduce verbose logging from uvicorn and fastapi
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

    # SQLAlchemy - show SQL only in DEBUG mode
    if app_log_level.upper() == "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    # httpx/httpcore (used by Claude SDK)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # websockets
    logging.getLogger("websockets").setLevel(logging.WARNING)

    # asyncio
    logging.getLogger("asyncio").setLevel(logging.WARNING)


__all__ = [
    "setup_logging",
    "StructuredFormatter",
    "ConsoleFormatter",
]
