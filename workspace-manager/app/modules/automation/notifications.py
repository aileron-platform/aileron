"""Best-effort one-shot delivery for terminal Automation executions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.modules.automation.webhook_delivery import DeliveryResult, deliver_webhook

logger = logging.getLogger(__name__)


class AutomationNotificationService:
    """Build and deliver the minimal approved terminal payload."""

    def __init__(
        self, *, deliver: Callable[..., DeliveryResult] = deliver_webhook
    ) -> None:
        self.deliver = deliver

    def deliver_terminal(
        self, *, execution: Any, notification_config: dict[str, Any]
    ) -> str | None:
        target = self._target(execution, notification_config)
        if target is None:
            return None
        try:
            result = self.deliver(
                target,
                self._payload(execution),
                f"automation-execution:{execution.id}",
                max_attempts=1,
            )
        except Exception as exc:
            logger.warning(
                "Automation notification delivery failed for execution_id=%s error=%s",
                execution.id,
                exc.__class__.__name__,
            )
            return "failed"
        if result.delivered:
            return "delivered"
        logger.warning(
            "Automation notification delivery failed for execution_id=%s error=%s",
            execution.id,
            result.error,
        )
        return "failed"

    @staticmethod
    def _target(execution: Any, config: dict[str, Any]) -> str | None:
        if execution.trigger not in {"cron", "every", "at"}:
            return None
        if execution.status == "success":
            target = config.get("delivery_webhook_url")
        elif execution.status == "failed":
            target = config.get("failure_destination") or config.get(
                "delivery_webhook_url"
            )
        else:
            return None
        return str(target) if target else None

    @classmethod
    def _payload(cls, execution: Any) -> dict[str, Any]:
        return {
            "jobId": execution.job_id,
            "executionId": execution.id,
            "status": execution.status,
            "errorCode": execution.error_code,
            "scheduledFor": cls._iso(execution.scheduled_for),
            "startedAt": cls._iso(execution.started_at),
            "finishedAt": cls._iso(execution.finished_at),
        }

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None


__all__ = ["AutomationNotificationService"]
