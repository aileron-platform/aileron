"""自動化任務執行日誌記錄器"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger("automation.execution")


class AutomationExecutionLogger:
    """自動化任務執行日誌記錄器，提供結構化的執行日誌追蹤"""

    def __init__(self, execution_id: str, job_id: str, workspace_id: Optional[str] = None):
        """
        初始化執行日誌記錄器

        Args:
            execution_id: 執行 ID
            job_id: 任務 ID
            workspace_id: 工作區 ID（可選）
        """
        self.execution_id = execution_id
        self.job_id = job_id
        self.workspace_id = workspace_id
        self.logs: list[dict[str, Any]] = []

    def log(
        self,
        level: str,
        message: str,
        **context: Any
    ) -> None:
        """
        記錄執行日誌

        Args:
            level: 日誌級別 (INFO, WARNING, ERROR, DEBUG)
            message: 日誌訊息
            **context: 額外的上下文資訊
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.upper(),
            "message": message,
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            **context
        }

        if self.workspace_id:
            log_entry["workspace_id"] = self.workspace_id

        self.logs.append(log_entry)

        # 同時寫入標準日誌
        log_method = getattr(logger, level.lower(), logger.info)
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message = (
            f"{message} - execution_id={self.execution_id}, job_id={self.job_id}"
        )
        if context_str:
            log_message += f", {context_str}"

        log_method(log_message)

    def info(self, message: str, **context: Any) -> None:
        """記錄 INFO 級別日誌"""
        self.log("INFO", message, **context)

    def warning(self, message: str, **context: Any) -> None:
        """記錄 WARNING 級別日誌"""
        self.log("WARNING", message, **context)

    def error(self, message: str, **context: Any) -> None:
        """記錄 ERROR 級別日誌"""
        self.log("ERROR", message, **context)

    def debug(self, message: str, **context: Any) -> None:
        """記錄 DEBUG 級別日誌"""
        self.log("DEBUG", message, **context)

    def get_logs(self) -> list[dict[str, Any]]:
        """獲取所有日誌"""
        return self.logs

    def to_metadata(self) -> dict[str, Any]:
        """
        轉換為元數據格式，可存儲到 execution_metadata

        Returns:
            包含日誌資訊的字典
        """
        return {
            "execution_logs": self.logs,
            "total_logs": len(self.logs),
            "log_levels": list(set(log["level"] for log in self.logs)),
            "has_errors": any(log["level"] == "ERROR" for log in self.logs),
            "has_warnings": any(log["level"] == "WARNING" for log in self.logs),
        }

    def get_summary(self) -> str:
        """
        獲取日誌摘要

        Returns:
            日誌摘要字串
        """
        total = len(self.logs)
        errors = sum(1 for log in self.logs if log["level"] == "ERROR")
        warnings = sum(1 for log in self.logs if log["level"] == "WARNING")

        parts = [f"共 {total} 條日誌"]
        if errors > 0:
            parts.append(f"{errors} 個錯誤")
        if warnings > 0:
            parts.append(f"{warnings} 個警告")

        return "，".join(parts)


__all__ = ["AutomationExecutionLogger"]

