"""Helpers for authenticating tests through opaque Manager sessions."""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.db import models as db_models
from app.modules.auth import middleware
from app.modules.auth.session import ManagerSessionService


def find_session_for_handle(
    db: Session,
    handle: str,
) -> db_models.ManagerSession | None:
    """Find persisted test state for an issued opaque handle."""

    return db.scalar(
        select(db_models.ManagerSession).where(
            db_models.ManagerSession.handle_hash
            == hashlib.sha256(handle.encode("utf-8")).hexdigest()
        )
    )


def session_for_handle(db: Session, handle: str) -> db_models.ManagerSession:
    """Return persisted test state for an issued opaque handle."""

    stored = find_session_for_handle(db, handle)
    assert stored is not None
    return stored


def csrf_token_for_handle(db: Session, handle: str) -> str:
    """Read CSRF evidence at the test boundary without a production resolver."""

    return session_for_handle(db, handle).csrf_token


def authenticate_client_as(client: TestClient, user: db_models.User) -> None:
    """Bind a real Manager session for the supplied local user to a test client."""
    with middleware.SessionLocal() as db:
        service = ManagerSessionService(db)
        issued = service.create(
            user_id=user.id,
            issuer=user.oidc_issuer or "https://oidc.test.example",
            subject=user.oidc_subject or f"subject-{user.id}",
            authentication_context={},
        )
        csrf_token = csrf_token_for_handle(db, issued.handle)

    client.cookies.set(
        middleware.SESSION_COOKIE_NAME,
        issued.handle,
        domain="aileron.test",
        path="/api/v1",
    )
    client.headers.update(
        {
            "Origin": "https://aileron.test",
            "X-CSRF-Token": csrf_token,
        }
    )
