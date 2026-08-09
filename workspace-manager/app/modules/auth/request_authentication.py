"""Deep module for authenticating Manager HTTP requests."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.identity.platform_role import normalize_platform_role
from app.modules.identity.user_authorization_policy import UserAuthorizationPolicy

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
MAX_TOUCH_WINDOW = timedelta(seconds=60)


class SessionFactory(Protocol):
    """Create a short-lived authentication database session."""

    def __call__(self) -> Session: ...


@dataclass(frozen=True, slots=True)
class ManagerRequestEvidence:
    """Untrusted HTTP evidence accepted by the authentication module."""

    session_handle: str | None
    method: str
    origin: str | None
    csrf_token: str | None


@dataclass(frozen=True, slots=True)
class AuthenticatedManagerUser:
    """Immutable User projection exposed to authenticated consumers."""

    id: str
    username: str
    email: str | None
    display_name: str | None


@dataclass(frozen=True, slots=True)
class AuthenticatedManagerRequest:
    """Immutable authentication result shared by one Manager request."""

    session_id: str
    user: AuthenticatedManagerUser
    actor: AuthorizationActor
    csrf_token: str
    absolute_expires_at: datetime


class ManagerRequestAuthenticationError(Exception):
    """Stable HTTP classification emitted by request authentication."""

    def __init__(self, *, status_code: int, error_code: str) -> None:
        super().__init__(error_code)
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class _AuthenticationProjection:
    session_id: str
    session_issuer: str
    session_subject: str
    csrf_token: str
    last_activity_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    user_id: str
    username: str
    email: str | None
    display_name: str | None
    user_issuer: str | None
    user_subject: str | None
    is_active: bool
    identity_enabled: bool
    sync_status: str
    platform_role: str | None
    role_status: str
    role_issues: list[str]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ManagerRequestAuthentication:
    """Authenticate one request with one indexed Session and User projection."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        platform_public_origin: str,
        policy: UserAuthorizationPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._platform_public_origin = platform_public_origin
        self._policy = policy or UserAuthorizationPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def authenticate(
        self,
        evidence: ManagerRequestEvidence,
    ) -> AuthenticatedManagerRequest:
        handle = evidence.session_handle
        if not isinstance(handle, str) or not handle:
            self._reject(401, "MANAGER_SESSION_REQUIRED")

        with self._session_factory() as db:
            projection = self._load_projection(db, handle)
            if projection is None:
                self._reject(401, "MANAGER_SESSION_REQUIRED")

            now = _utc(self._clock())
            if (
                now >= _utc(projection.idle_expires_at)
                or now >= _utc(projection.absolute_expires_at)
                or projection.session_issuer != projection.user_issuer
                or projection.session_subject != projection.user_subject
            ):
                self._reject(401, "MANAGER_SESSION_REQUIRED")

            if not self._policy.is_authorized(projection):
                self._reject(403, "PLATFORM_AUTHORIZATION_DENIED")

            if evidence.method.upper() not in SAFE_METHODS:
                if evidence.origin != self._platform_public_origin:
                    self._reject(403, "MANAGER_SESSION_ORIGIN_INVALID")
                if not evidence.csrf_token or not hmac.compare_digest(
                    projection.csrf_token,
                    evidence.csrf_token,
                ):
                    self._reject(403, "MANAGER_SESSION_CSRF_INVALID")

            self._touch_if_due(db, projection=projection, now=now)

        role = normalize_platform_role(projection.platform_role)
        if role is None:  # Policy already rejects this; keep construction total.
            self._reject(403, "PLATFORM_AUTHORIZATION_DENIED")
        return AuthenticatedManagerRequest(
            session_id=projection.session_id,
            user=AuthenticatedManagerUser(
                id=projection.user_id,
                username=projection.username,
                email=projection.email,
                display_name=projection.display_name,
            ),
            actor=AuthorizationActor(
                user_id=projection.user_id,
                platform_role=role,
            ),
            csrf_token=projection.csrf_token,
            absolute_expires_at=_utc(projection.absolute_expires_at),
        )

    @staticmethod
    def _load_projection(
        db: Session,
        handle: str,
    ) -> _AuthenticationProjection | None:
        session = db_models.ManagerSession
        user = db_models.User
        row = (
            db.execute(
                select(
                    session.id.label("session_id"),
                    session.oidc_issuer.label("session_issuer"),
                    session.oidc_subject.label("session_subject"),
                    session.csrf_token,
                    session.last_activity_at,
                    session.idle_expires_at,
                    session.absolute_expires_at,
                    user.id.label("user_id"),
                    user.username,
                    user.email,
                    user.display_name,
                    user.oidc_issuer.label("user_issuer"),
                    user.oidc_subject.label("user_subject"),
                    user.is_active,
                    user.identity_enabled,
                    user.sync_status,
                    user.platform_role,
                    user.role_status,
                    user.role_issues,
                )
                .join(user, user.id == session.user_id)
                .where(
                    session.handle_hash
                    == hashlib.sha256(handle.encode("utf-8")).hexdigest()
                )
            )
            .mappings()
            .one_or_none()
        )
        return _AuthenticationProjection(**row) if row is not None else None

    def _touch_if_due(
        self,
        db: Session,
        *,
        projection: _AuthenticationProjection,
        now: datetime,
    ) -> None:
        idle_timeout = _utc(projection.idle_expires_at) - _utc(
            projection.last_activity_at
        )
        touch_window = min(MAX_TOUCH_WINDOW, idle_timeout / 4)
        touch_cutoff = now - touch_window
        if _utc(projection.last_activity_at) > touch_cutoff:
            return

        absolute_expires_at = _utc(projection.absolute_expires_at)
        db.execute(
            update(db_models.ManagerSession)
            .where(
                db_models.ManagerSession.id == projection.session_id,
                db_models.ManagerSession.last_activity_at <= touch_cutoff,
                db_models.ManagerSession.absolute_expires_at > now,
            )
            .values(
                last_activity_at=now,
                idle_expires_at=min(now + idle_timeout, absolute_expires_at),
            )
        )
        db.commit()

    @staticmethod
    def _reject(status_code: int, error_code: str) -> None:
        raise ManagerRequestAuthenticationError(
            status_code=status_code,
            error_code=error_code,
        )


__all__ = [
    "AuthenticatedManagerRequest",
    "AuthenticatedManagerUser",
    "ManagerRequestAuthentication",
    "ManagerRequestAuthenticationError",
    "ManagerRequestEvidence",
]
