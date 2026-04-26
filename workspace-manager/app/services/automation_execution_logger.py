"""Automation task execution logger"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger("automation.execution")


class AutomationExecutionLogger:
    """Automation task execution logger, provides structured execution log tracking"""

    def __init__(self, execution_id: str, job_id: str, workspace_id: Optional[str] = None):
        """
        Initialize execution logger

        Args:
            execution_id: Execution ID
            job_id: Task ID
            workspace_id: Workspace ID (optional)
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
        Record execution log

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            message: Log message
            **context: Additional context information
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

        # Also write to standard log
        log_method = getattr(logger, level.lower(), logger.info)
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message = (
            f"{message} - execution_id={self.execution_id}, job_id={self.job_id}"
        )
        if context_str:
            log_message += f", {context_str}"

        log_method(log_message)

    def info(self, message: str, **context: Any) -> None:
        """Record INFO level log"""
        self.log("INFO", message, **context)

    def warning(self, message: str, **context: Any) -> None:
        """Record WARNING level log"""
        self.log("WARNING", message, **context)

    def error(self, message: str, **context: Any) -> None:
        """Record ERROR level log"""
        self.log("ERROR", message, **context)

    def debug(self, message: str, **context: Any) -> None:
        """Record DEBUG level log"""
        self.log("DEBUG", message, **context)

    def get_logs(self) -> list[dict[str, Any]]:
        """Get all logs"""
        return self.logs

    def to_metadata(self) -> dict[str, Any]:
        """
        Convert to metadata format, can be stored to execution_metadata

        Returns:
            Dictionary containing log information
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
        Get log summary

        Returns:
            Log summary string
        """
        total = len(self.logs)
        errors = sum(1 for log in self.logs if log["level"] == "ERROR")
        warnings = sum(1 for log in self.logs if log["level"] == "WARNING")

        parts = [f"Total {total} logs"]
        if errors > 0:
            parts.append(f"{errors} errors")
        if warnings > 0:
            parts.append(f"{warnings} warnings")

        return ", ".join(parts)


__all__ = ["AutomationExecutionLogger"]

