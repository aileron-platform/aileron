from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.modules.automation.schedules import (
    AutomationScheduleError,
    AutomationScheduleService,
)

REFERENCE = datetime(2026, 7, 15, 10, 15, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("trigger", ["manual", "webhook"])
def test_manual_and_webhook_require_empty_schedule(trigger: str) -> None:
    service = AutomationScheduleService()

    assert (
        service.validate_and_next_run(
            trigger=trigger, schedule="", exact=False, reference=REFERENCE
        )
        is None
    )
    with pytest.raises(AutomationScheduleError) as exc:
        service.validate_and_next_run(
            trigger=trigger, schedule="unexpected", exact=False, reference=REFERENCE
        )
    assert exc.value.code == "automation_schedule_invalid"


@pytest.mark.parametrize(
    ("trigger", "schedule", "expected"),
    [
        ("every", "20m", REFERENCE + timedelta(minutes=20)),
        ("at", "20m", REFERENCE + timedelta(minutes=20)),
        ("at", "2026-07-15T11:00:00Z", datetime(2026, 7, 15, 11, tzinfo=timezone.utc)),
        ("cron", "0 11 * * *", datetime(2026, 7, 15, 11, tzinfo=timezone.utc)),
    ],
)
def test_supported_schedules_return_future_occurrence(
    trigger: str, schedule: str, expected: datetime
) -> None:
    service = AutomationScheduleService(
        offset_provider=lambda: 0, system_timezone="UTC"
    )

    assert (
        service.validate_and_next_run(
            trigger=trigger, schedule=schedule, exact=True, reference=REFERENCE
        )
        == expected
    )


@pytest.mark.parametrize(
    ("trigger", "schedule"),
    [("cron", "bad cron"), ("every", "0m"), ("at", "bad timestamp")],
)
def test_invalid_schedule_uses_stable_code(trigger: str, schedule: str) -> None:
    with pytest.raises(AutomationScheduleError) as exc:
        AutomationScheduleService().validate_and_next_run(
            trigger=trigger, schedule=schedule, exact=False, reference=REFERENCE
        )
    assert exc.value.code == "automation_schedule_invalid"


def test_past_at_uses_expired_code() -> None:
    with pytest.raises(AutomationScheduleError) as exc:
        AutomationScheduleService().next_strictly_after(
            trigger="at",
            schedule="2026-07-15T09:00:00Z",
            exact=False,
            reference=REFERENCE,
        )
    assert exc.value.code == "automation_schedule_expired"


@pytest.mark.parametrize("offset", [0, 300])
def test_non_exact_staggers_only_whole_hour_occurrence(offset: int) -> None:
    service = AutomationScheduleService(offset_provider=lambda: offset)
    whole_hour = service.next_strictly_after(
        trigger="cron", schedule="0 * * * *", exact=False, reference=REFERENCE
    )
    non_whole_hour = service.next_strictly_after(
        trigger="cron", schedule="30 * * * *", exact=False, reference=REFERENCE
    )

    assert whole_hour == datetime(2026, 7, 15, 11, tzinfo=timezone.utc) + timedelta(
        seconds=offset
    )
    assert non_whole_hour == datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc)


def test_exact_never_staggers() -> None:
    result = AutomationScheduleService(offset_provider=lambda: 300).next_strictly_after(
        trigger="cron", schedule="0 * * * *", exact=True, reference=REFERENCE
    )
    assert result == datetime(2026, 7, 15, 11, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("trigger", "schedule", "reference"),
    [
        (
            "cron",
            "0 9 * * *",
            datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc),
        ),
        (
            "every",
            "1h",
            datetime(2026, 7, 15, 2, 15, tzinfo=timezone.utc),
        ),
    ],
)
def test_non_exact_staggers_local_whole_hour_in_non_hour_timezone(
    trigger: str, schedule: str, reference: datetime
) -> None:
    result = AutomationScheduleService(
        offset_provider=lambda: 120, system_timezone="Asia/Kathmandu"
    ).next_strictly_after(
        trigger=trigger,
        schedule=schedule,
        exact=False,
        reference=reference,
    )

    assert result == datetime(2026, 7, 15, 3, 17, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("trigger", "schedule", "reference"),
    [
        (
            "cron",
            "45 9 * * *",
            datetime(2026, 7, 15, 3, 30, tzinfo=timezone.utc),
        ),
        (
            "every",
            "1h",
            datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc),
        ),
    ],
)
def test_non_exact_does_not_stagger_local_non_whole_hour_at_utc_whole_hour(
    trigger: str, schedule: str, reference: datetime
) -> None:
    result = AutomationScheduleService(
        offset_provider=lambda: 120, system_timezone="Asia/Kathmandu"
    ).next_strictly_after(
        trigger=trigger,
        schedule=schedule,
        exact=False,
        reference=reference,
    )

    assert result == datetime(2026, 7, 15, 4, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("trigger", "schedule", "reference"),
    [
        (
            "cron",
            "0 9 * * *",
            datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc),
        ),
        (
            "every",
            "1h",
            datetime(2026, 7, 15, 2, 15, tzinfo=timezone.utc),
        ),
    ],
)
def test_exact_does_not_stagger_local_whole_hour_in_non_hour_timezone(
    trigger: str, schedule: str, reference: datetime
) -> None:
    result = AutomationScheduleService(
        offset_provider=lambda: 120, system_timezone="Asia/Kathmandu"
    ).next_strictly_after(
        trigger=trigger,
        schedule=schedule,
        exact=True,
        reference=reference,
    )

    assert result == datetime(2026, 7, 15, 3, 15, tzinfo=timezone.utc)


def test_cron_is_interpreted_in_injected_system_timezone() -> None:
    service = AutomationScheduleService(
        offset_provider=lambda: 0, system_timezone="Asia/Taipei"
    )
    result = service.next_strictly_after(
        trigger="cron",
        schedule="0 9 * * *",
        exact=True,
        reference=datetime(2026, 7, 15, 0, 30, tzinfo=timezone.utc),
    )
    assert result == datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc)


def test_naive_at_is_interpreted_in_injected_system_timezone() -> None:
    service = AutomationScheduleService(system_timezone="Asia/Taipei")
    result = service.next_strictly_after(
        trigger="at",
        schedule="2026-07-15T09:00:00",
        exact=True,
        reference=datetime(2026, 7, 15, 0, 30, tzinfo=timezone.utc),
    )
    assert result == datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc)


def test_non_utc_reference_is_compared_as_same_instant() -> None:
    service = AutomationScheduleService(system_timezone="Asia/Taipei")
    result = service.next_strictly_after(
        trigger="cron",
        schedule="0 9 * * *",
        exact=True,
        reference=datetime(2026, 7, 15, 8, 30, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert result == datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc)


def test_explicit_offset_at_remains_absolute() -> None:
    service = AutomationScheduleService(system_timezone="Asia/Taipei")
    result = service.next_strictly_after(
        trigger="at",
        schedule="2026-07-15T09:00:00+02:00",
        exact=True,
        reference=datetime(2026, 7, 15, 0, 30, tzinfo=timezone.utc),
    )
    assert result == datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc)


def test_structural_validation_allows_past_at_without_calculating_occurrence() -> None:
    service = AutomationScheduleService(system_timezone="Asia/Taipei")
    assert service.validate(trigger="at", schedule="2020-01-01T00:00:00") is None
