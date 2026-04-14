"""日誌配置模組

提供統一的日誌配置，支援：
- 結構化日誌（JSON 格式，適合生產環境）
- 控制台日誌（人類可讀格式，適合開發環境）
- 日誌等級控制
- 第三方庫日誌過濾
"""

import logging
import os
import sys
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """結構化日誌格式化器（JSON 格式）"""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加額外欄位
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id

        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id

        # 添加異常資訊
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加來源位置
        if record.levelno >= logging.WARNING:
            log_data["location"] = f"{record.filename}:{record.lineno}"

        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """控制台日誌格式化器（人類可讀格式）"""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        # 基本格式
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        name = record.name[-30:] if len(record.name) > 30 else record.name

        # 構建訊息
        message = record.getMessage()

        # 添加顏色
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            level = f"{color}{level}{self.RESET}"

        # 添加上下文
        context_parts = []
        if hasattr(record, "request_id"):
            context_parts.append(f"req={record.request_id[:8]}")
        if hasattr(record, "session_id"):
            context_parts.append(f"sess={record.session_id[:8]}")

        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        formatted = f"{timestamp} | {level} | {name}{context} | {message}"

        # 添加異常資訊
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def setup_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """設置日誌配置

    Args:
        config: 配置字典，支援以下選項：
            - log_level: 日誌等級 (DEBUG, INFO, WARNING, ERROR)
            - log_format: 日誌格式 ("json" 或 "console")
            - use_colors: 是否使用顏色（僅 console 格式）
    """
    config = config or {}

    # 從環境變數或配置取得設定
    log_level = config.get("log_level", os.getenv("LOG_LEVEL", "INFO"))
    log_format = config.get("log_format", os.getenv("LOG_FORMAT", "console"))
    use_colors = config.get("use_colors", os.getenv("LOG_COLORS", "true").lower() == "true")

    # 設定根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 清除現有 handlers
    root_logger.handlers.clear()

    # 建立 handler
    handler = logging.StreamHandler(sys.stdout)

    # 選擇格式化器
    if log_format.lower() == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(ConsoleFormatter(use_colors=use_colors))

    root_logger.addHandler(handler)

    # 配置第三方庫日誌等級
    _configure_third_party_loggers(log_level)

    logging.info(f"Logging configured: level={log_level}, format={log_format}")


def _configure_third_party_loggers(app_log_level: str) -> None:
    """配置第三方庫的日誌等級"""
    # 減少 uvicorn 和 fastapi 的詳細日誌
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

    # SQLAlchemy - 只在 DEBUG 模式下顯示 SQL
    if app_log_level.upper() == "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    # httpx/httpcore（Claude SDK 使用）
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # websockets
    logging.getLogger("websockets").setLevel(logging.WARNING)

    # asyncio
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """取得 logger 實例

    Args:
        name: Logger 名稱（通常使用 __name__）

    Returns:
        Logger 實例
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """帶有上下文的 Logger Adapter

    可以添加 request_id, session_id 等上下文資訊。
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_context_logger(
    name: str,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> LoggerAdapter:
    """取得帶有上下文的 Logger

    Args:
        name: Logger 名稱
        request_id: 請求 ID
        session_id: 會話 ID
        task_id: 任務 ID

    Returns:
        LoggerAdapter 實例
    """
    logger = logging.getLogger(name)
    extra = {}
    if request_id:
        extra["request_id"] = request_id
    if session_id:
        extra["session_id"] = session_id
    if task_id:
        extra["task_id"] = task_id

    return LoggerAdapter(logger, extra)


__all__ = [
    "setup_logging",
    "get_logger",
    "get_context_logger",
    "LoggerAdapter",
    "StructuredFormatter",
    "ConsoleFormatter",
]
