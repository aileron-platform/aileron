"""Focused tests for one-shot Automation terminal notification."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.modules.automation.notifications import AutomationNotificationService
from app.modules.automation.webhook_delivery import DeliveryResult


def _execution(*, status: str, trigger: str):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="execution-1",
        job_id="job-1",
        status=status,
        trigger=trigger,
        error_code="agent_failed" if status == "failed" else None,
        error_message="secret raw error",
        scheduled_for=now,
        started_at=now,
        finished_at=now,
        notification_status=None,
    )


@pytest.mark.parametrize(
    ("status", "trigger", "config", "expected_url"),
    [
        (
            "success",
            "cron",
            {"delivery_webhook_url": "https://ok.example/hook"},
            "https://ok.example/hook",
        ),
        (
            "failed",
            "every",
            {"delivery_webhook_url": "https://fallback.example/hook"},
            "https://fallback.example/hook",
        ),
        (
            "failed",
            "at",
            {"failure_destination": "https://fail.example/hook"},
            "https://fail.example/hook",
        ),
        (
            "cancelled",
            "cron",
            {"delivery_webhook_url": "https://ok.example/hook"},
            None,
        ),
        (
            "success",
            "manual",
            {"delivery_webhook_url": "https://ok.example/hook"},
            None,
        ),
        (
            "failed",
            "webhook",
            {"failure_destination": "https://fail.example/hook"},
            None,
        ),
        ("success", "cron", {}, None),
    ],
)
def test_notification_matrix_and_minimal_payload(
    status, trigger, config, expected_url
) -> None:
    calls = []

    def deliver(url, payload, idempotency_key, **kwargs):
        calls.append((url, payload, idempotency_key, kwargs))
        return DeliveryResult(True, status_code=204, attempts=1)

    execution = _execution(status=status, trigger=trigger)
    service = AutomationNotificationService(deliver=deliver)
    result = service.deliver_terminal(execution=execution, notification_config=config)

    if expected_url is None:
        assert result is None
        assert calls == []
        return
    assert result == "delivered"
    assert len(calls) == 1
    url, payload, idempotency_key, kwargs = calls[0]
    assert url == expected_url
    assert idempotency_key == "automation-execution:execution-1"
    assert kwargs["max_attempts"] == 1
    assert set(payload) == {
        "jobId",
        "executionId",
        "status",
        "errorCode",
        "scheduledFor",
        "startedAt",
        "finishedAt",
    }
    assert "secret raw error" not in str(payload)


def test_notification_failure_is_best_effort(monkeypatch) -> None:
    execution = _execution(status="failed", trigger="cron")
    warnings = []
    monkeypatch.setattr(
        "app.modules.automation.notifications.logger.warning",
        lambda message, *args: warnings.append(message % args),
    )

    def deliver(*args, **kwargs):
        return DeliveryResult(False, error="transport", attempts=1)

    service = AutomationNotificationService(deliver=deliver)
    assert (
        service.deliver_terminal(
            execution=execution,
            notification_config={"failure_destination": "https://fail.example/hook"},
        )
        == "failed"
    )
    assert execution.status == "failed"
    assert "Automation notification delivery failed" in warnings[0]


def test_notification_transport_exception_is_best_effort(monkeypatch) -> None:
    execution = _execution(status="failed", trigger="cron")
    warnings = []
    monkeypatch.setattr(
        "app.modules.automation.notifications.logger.warning",
        lambda message, *args: warnings.append(message % args),
    )

    def deliver(*args, **kwargs):
        raise RuntimeError("transport exploded")

    service = AutomationNotificationService(deliver=deliver)
    assert (
        service.deliver_terminal(
            execution=execution,
            notification_config={"failure_destination": "https://fail.example/hook"},
        )
        == "failed"
    )
    assert execution.status == "failed"
    assert "Automation notification delivery failed" in warnings[0]
