"""Opaque PostgreSQL-backed Manager sessions and session-bound CSRF tokens."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import models as db_models

DEFAULT_IDLE_TIMEOUT = timedelta(minutes=30)
DEFAULT_ABSOLUTE_LIFETIME = timedelta(hours=8)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedManagerSession:
    """Opaque material returned only to the browser-facing boundary."""

    handle: str
    absolute_expires_at: datetime


class ManagerSessionService:
    """Create and revoke Manager browser sessions."""

    def __init__(
        self,
        db: Session,
        *,
        idle_timeout: timedelta = DEFAULT_IDLE_TIMEOUT,
        absolute_lifetime: timedelta = DEFAULT_ABSOLUTE_LIFETIME,
    ) -> None:
        if idle_timeout <= timedelta(0) or idle_timeout > DEFAULT_IDLE_TIMEOUT:
            raise ValueError("Manager session idle timeout must be within 30 minutes")
        if (
            absolute_lifetime <= timedelta(0)
            or absolute_lifetime > DEFAULT_ABSOLUTE_LIFETIME
        ):
            raise ValueError("Manager session absolute lifetime must be within 8 hours")
        self.db = db
        self.idle_timeout = idle_timeout
        self.absolute_lifetime = absolute_lifetime

    def create(
        self,
        *,
        user_id: str,
        issuer: str,
        subject: str,
        authentication_context: dict[str, object],
    ) -> IssuedManagerSession:
        now = datetime.now(timezone.utc)
        handle = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        record = db_models.ManagerSession(
            id=str(uuid4()),
            handle_hash=_digest(handle),
            csrf_token=csrf_token,
            user_id=user_id,
            oidc_issuer=issuer,
            oidc_subject=subject,
            authentication_context=dict(authentication_context),
            created_at=now,
            last_activity_at=now,
            idle_expires_at=now + self.idle_timeout,
            absolute_expires_at=now + self.absolute_lifetime,
        )
        self.db.add(record)
        self.db.commit()
        return IssuedManagerSession(
            handle=handle,
            absolute_expires_at=record.absolute_expires_at,
        )

    def revoke_by_id(self, session_id: str) -> None:
        """Revoke a session already authenticated by the request module."""

        self.db.execute(
            delete(db_models.ManagerSession).where(
                db_models.ManagerSession.id == session_id
            )
        )
        self.db.commit()


__all__ = [
    "DEFAULT_ABSOLUTE_LIFETIME",
    "DEFAULT_IDLE_TIMEOUT",
    "IssuedManagerSession",
    "ManagerSessionService",
]
