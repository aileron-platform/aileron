"""Automation schedule validation and next-occurrence policy."""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

from app.config.settings import get_settings

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class AutomationScheduleError(ValueError):
    """Stable schedule policy failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AutomationScheduleService:
    """Validate schedules and calculate timezone-aware future occurrences."""

    def __init__(
        self,
        offset_provider: Callable[[], int] | None = None,
        system_timezone: str | ZoneInfo | None = None,
    ) -> None:
        self._offset_provider = offset_provider or (lambda: random.randint(0, 300))
        timezone_value = system_timezone or get_settings().TZ
        self._system_timezone = (
            timezone_value
            if isinstance(timezone_value, ZoneInfo)
            else ZoneInfo(timezone_value)
        )

    def validate(self, *, trigger: str, schedule: str) -> None:
        """Validate schedule structure without requiring a future occurrence."""
        normalized = schedule.strip()
        if trigger in {"manual", "webhook"}:
            if normalized:
                raise AutomationScheduleError("automation_schedule_invalid")
            return
        if trigger == "every":
            if self._parse_duration(normalized) is None:
                raise AutomationScheduleError("automation_schedule_invalid")
            return
        if trigger == "at":
            if (
                self._parse_duration(normalized) is None
                and self._parse_absolute_at(normalized) is None
            ):
                raise AutomationScheduleError("automation_schedule_invalid")
            return
        if trigger == "cron":
            if not normalized or not croniter.is_valid(normalized):
                raise AutomationScheduleError("automation_schedule_invalid")
            return
        raise AutomationScheduleError("automation_schedule_invalid")

    def validate_and_next_run(
        self, *, trigger: str, schedule: str, exact: bool, reference: datetime
    ) -> datetime | None:
        self.validate(trigger=trigger, schedule=schedule)
        return self._next(
            trigger=trigger, schedule=schedule, exact=exact, reference=reference
        )

    def next_strictly_after(
        self, *, trigger: str, schedule: str, exact: bool, reference: datetime
    ) -> datetime | None:
        self.validate(trigger=trigger, schedule=schedule)
        return self._next(
            trigger=trigger, schedule=schedule, exact=exact, reference=reference
        )

    def _next(
        self,
        *,
        trigger: str,
        schedule: str,
        exact: bool,
        reference: datetime,
    ) -> datetime | None:
        reference_utc = self._utc(reference)
        normalized = schedule.strip()
        if trigger in {"manual", "webhook"}:
            return None
        if trigger == "every":
            duration = self._parse_duration(normalized)
            if duration is None:
                raise AutomationScheduleError("automation_schedule_invalid")
            return self._stagger(reference_utc + duration, exact=exact)
        if trigger == "at":
            occurrence = self._parse_at(normalized, reference_utc)
            if occurrence is None:
                raise AutomationScheduleError("automation_schedule_invalid")
            if occurrence <= reference_utc:
                raise AutomationScheduleError("automation_schedule_expired")
            return occurrence
        if trigger == "cron":
            local_reference = reference_utc.astimezone(self._system_timezone)
            try:
                occurrence = croniter(normalized, local_reference).get_next(datetime)
            except (CroniterBadCronError, CroniterBadDateError, ValueError) as exc:
                raise AutomationScheduleError("automation_schedule_invalid") from exc
            return self._stagger(self._utc(occurrence), exact=exact)
        raise AutomationScheduleError("automation_schedule_invalid")

    def _stagger(self, occurrence: datetime, *, exact: bool) -> datetime:
        occurrence_utc = self._utc(occurrence)
        local_occurrence = occurrence_utc.astimezone(self._system_timezone)
        if exact or local_occurrence.minute != 0 or local_occurrence.second != 0:
            return occurrence_utc
        offset = self._offset_provider()
        if not 0 <= offset <= 300:
            raise ValueError(
                "offset_provider must return an integer from 0 through 300"
            )
        return occurrence_utc + timedelta(seconds=offset)

    @staticmethod
    def _parse_duration(value: str) -> timedelta | None:
        match = _DURATION_RE.match(value)
        if not match:
            return None
        amount = int(match.group(1))
        if amount <= 0:
            return None
        return timedelta(seconds=amount * _UNIT_SECONDS[match.group(2).lower()])

    def _parse_at(self, value: str, reference: datetime) -> datetime | None:
        duration = self._parse_duration(value)
        if duration is not None:
            return reference + duration
        return self._parse_absolute_at(value)

    def _parse_absolute_at(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self._system_timezone)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


__all__ = ["AutomationScheduleError", "AutomationScheduleService"]
