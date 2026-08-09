"""Independent audit persistence for Platform Admin resource overrides."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.modules.audit.events import AuditEventService

OverrideTargetType = Literal["workspace", "knowledge_base"]
OverrideAuditResult = Literal["success", "failure"]


@dataclass(frozen=True)
class PlatformAdminOverrideAuditRecord:
    """Complete structured evidence for one Admin resource override."""

    actor_user_id: str
    target_type: OverrideTargetType
    target_id: str
    operation: str
    result: OverrideAuditResult
    error_code: str | None


class PlatformAdminOverrideAuditWriter(Protocol):
    """Injectable persistence boundary used by authorization policy."""

    def write(self, record: PlatformAdminOverrideAuditRecord) -> None:
        """Persist one Admin override audit record."""


class IndependentPlatformAdminOverrideAuditWriter:
    """Persist override evidence in a transaction independent of the caller."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self._session_factory = session_factory

    def write(self, record: PlatformAdminOverrideAuditRecord) -> None:
        correlation_id = str(uuid4())
        with self._session_factory() as audit_db:
            try:
                AuditEventService(audit_db).record(
                    event_type="authorization.platform_admin_override",
                    actor_type="user",
                    actor_id=record.actor_user_id,
                    actor_user_id=record.actor_user_id,
                    target_type=record.target_type,
                    target_id=record.target_id,
                    action=record.operation,
                    result=record.result,
                    error_code=record.error_code,
                    correlation_id=correlation_id,
                    root_correlation_id=correlation_id,
                )
                audit_db.commit()
            except Exception:
                audit_db.rollback()
                raise
