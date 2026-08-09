"""Authoritative capacity risk, freshness, and storage-kind policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import case
from sqlalchemy.sql.elements import ColumnElement

from .models import CapacityRisk, WorkspaceStorageKind

GIB = 1024**3
WORKSPACE_STORAGE_KINDS: tuple[WorkspaceStorageKind, ...] = (
    "workspace_data",
    "runtime_home",
)


@dataclass(frozen=True)
class CapacityAssessment:
    risk: CapacityRisk
    utilization: float | None
    stale: bool


class CapacityGovernancePolicy:
    """Classify capacity consistently for projections and database filters."""

    warning_utilization = 0.80
    critical_utilization = 0.95
    stale_after = timedelta(hours=2)

    @classmethod
    def assess(
        cls,
        *,
        used_bytes: int | None,
        allocated_bytes: int | None,
        measured_at: datetime | None,
        now: datetime | None = None,
    ) -> CapacityAssessment:
        if used_bytes is None or measured_at is None:
            return CapacityAssessment("unknown", None, False)
        utilization = (
            used_bytes / allocated_bytes
            if allocated_bytes is not None and allocated_bytes > 0
            else None
        )
        current = now or datetime.now(timezone.utc)
        observed = (
            measured_at
            if measured_at.tzinfo is not None
            else measured_at.replace(tzinfo=timezone.utc)
        )
        if current - observed > cls.stale_after:
            return CapacityAssessment("stale", utilization, True)
        if utilization is None:
            return CapacityAssessment("normal", None, False)
        if utilization >= cls.critical_utilization:
            return CapacityAssessment("critical", utilization, False)
        if utilization >= cls.warning_utilization:
            return CapacityAssessment("warning", utilization, False)
        return CapacityAssessment("normal", utilization, False)

    @classmethod
    def assess_quota(cls, *, used_bytes: int, quota_bytes: int) -> CapacityAssessment:
        utilization = used_bytes / quota_bytes if quota_bytes > 0 else None
        if utilization is not None and utilization >= cls.critical_utilization:
            return CapacityAssessment("critical", utilization, False)
        if utilization is not None and utilization >= cls.warning_utilization:
            return CapacityAssessment("warning", utilization, False)
        return CapacityAssessment("normal", utilization, False)

    @staticmethod
    def highest(risks: Iterable[CapacityRisk]) -> CapacityRisk:
        priority = {"unknown": 0, "normal": 1, "stale": 2, "warning": 3, "critical": 4}
        values = list(risks)
        return max(values, key=priority.__getitem__) if values else "unknown"

    @classmethod
    def observation_risk_expression(
        cls,
        *,
        exists: Any,
        used_bytes: Any,
        allocated_bytes: Any,
        measured_at: Any,
        now: datetime | None = None,
    ) -> ColumnElement[str]:
        cutoff = cls._sql_now(now) - cls.stale_after
        utilization = used_bytes / allocated_bytes
        return case(
            (~exists, "unknown"),
            (measured_at < cutoff, "stale"),
            (
                (allocated_bytes > 0) & (utilization >= cls.critical_utilization),
                "critical",
            ),
            (
                (allocated_bytes > 0) & (utilization >= cls.warning_utilization),
                "warning",
            ),
            else_="normal",
        )

    @staticmethod
    def highest_risk_expression(
        risks: Iterable[ColumnElement[str]],
    ) -> ColumnElement[str]:
        values = list(risks)
        if not values:
            raise ValueError("At least one capacity risk expression is required")
        return case(
            (CapacityGovernancePolicy._any_equal(values, "critical"), "critical"),
            (CapacityGovernancePolicy._any_equal(values, "warning"), "warning"),
            (CapacityGovernancePolicy._any_equal(values, "stale"), "stale"),
            (CapacityGovernancePolicy._any_equal(values, "normal"), "normal"),
            else_="unknown",
        )

    @classmethod
    def quota_risk_expression(
        cls,
        *,
        used_bytes: Any,
        quota_bytes: Any,
    ) -> ColumnElement[str]:
        utilization = used_bytes / quota_bytes
        return case(
            (
                (quota_bytes > 0) & (utilization >= cls.critical_utilization),
                "critical",
            ),
            (
                (quota_bytes > 0) & (utilization >= cls.warning_utilization),
                "warning",
            ),
            else_="normal",
        )

    @staticmethod
    def require_workspace_storage_kind(value: str) -> WorkspaceStorageKind:
        if value not in WORKSPACE_STORAGE_KINDS:
            raise ValueError("Workspace storage kind is invalid")
        return value

    @staticmethod
    def require_expansion_bytes(value: int) -> int:
        if value <= 0 or value % GIB:
            raise ValueError("Workspace capacity must use a positive GiB boundary")
        return value

    @staticmethod
    def _any_equal(
        expressions: list[ColumnElement[str]], value: str
    ) -> ColumnElement[bool]:
        result = expressions[0] == value
        for expression in expressions[1:]:
            result = result | (expression == value)
        return result

    @staticmethod
    def _sql_now(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        return current.replace(tzinfo=None) if current.tzinfo is not None else current
