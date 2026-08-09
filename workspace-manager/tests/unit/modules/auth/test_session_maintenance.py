"""Behavior tests for Manager Session expiration maintenance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry
from sqlalchemy import delete, func, select

from app.db import models as db_models
from app.modules.auth import tasks as auth_tasks
from app.modules.auth.session import ManagerSessionService
from app.modules.auth.session_maintenance import cleanup_expired_sessions
from tests.helpers.manager_session import session_for_handle


def _issue_session(
    db,
    *,
    user: db_models.User,
    absolute_expires_at: datetime,
) -> str:
    issued = ManagerSessionService(db).create(
        user_id=user.id,
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        authentication_context={},
    )
    stored = session_for_handle(db, issued.handle)
    stored.absolute_expires_at = absolute_expires_at
    db.commit()
    return stored.id


def test_cleanup_expired_sessions_uses_a_bounded_absolute_expiry_batch(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    now = datetime.now(timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        for _ in range(3):
            _issue_session(
                db,
                user=user,
                absolute_expires_at=now - timedelta(seconds=1),
            )
        _issue_session(
            db,
            user=user,
            absolute_expires_at=now + timedelta(hours=1),
        )

        first_deleted = cleanup_expired_sessions(db, now=now, batch_size=2)
        second_deleted = cleanup_expired_sessions(db, now=now, batch_size=2)
        retry_deleted = cleanup_expired_sessions(db, now=now, batch_size=2)
        remaining = db.scalar(select(func.count(db_models.ManagerSession.id)))

    assert first_deleted == 2
    assert second_deleted == 1
    assert retry_deleted == 0
    assert remaining == 1


def test_cleanup_task_rolls_back_failed_batch_and_requests_retry(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    now = datetime.now(timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        session_id = _issue_session(
            db,
            user=user,
            absolute_expires_at=now - timedelta(seconds=1),
        )

    def delete_then_fail(db) -> int:
        db.execute(
            delete(db_models.ManagerSession).where(
                db_models.ManagerSession.id == session_id
            )
        )
        raise RuntimeError("transient cleanup failure")

    monkeypatch.setattr(auth_tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(auth_tasks, "cleanup_expired_sessions", delete_then_fail)
    retry = Mock(side_effect=Retry("scheduled retry"))
    monkeypatch.setattr(auth_tasks.cleanup_expired_manager_sessions, "retry", retry)

    assert not hasattr(auth_tasks.cleanup_expired_manager_sessions, "_orig_run")
    with pytest.raises(Retry):
        auth_tasks.cleanup_expired_manager_sessions.run()

    retry.assert_called_once()
    assert retry.call_args.kwargs["max_retries"] == 3
    assert isinstance(retry.call_args.kwargs["exc"], RuntimeError)
    with session_factory() as db:
        assert db.get(db_models.ManagerSession, session_id) is not None


def test_cleanup_rejects_non_positive_batch_without_writing(test_app) -> None:
    _, session_factory = test_app
    with session_factory() as db:
        with pytest.raises(ValueError, match="SESSION_CLEANUP_BATCH_SIZE_INVALID"):
            cleanup_expired_sessions(
                db,
                now=datetime.now(timezone.utc),
                batch_size=0,
            )


def test_cleanup_task_returns_deleted_count_for_one_bounded_batch(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    now = datetime.now(timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        _issue_session(
            db,
            user=user,
            absolute_expires_at=now - timedelta(seconds=1),
        )
        _issue_session(
            db=db,
            user=user,
            absolute_expires_at=now + timedelta(hours=1),
        )

    monkeypatch.setattr(auth_tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(
        auth_tasks,
        "cleanup_expired_sessions",
        lambda db: cleanup_expired_sessions(db, now=now, batch_size=1),
    )

    result = auth_tasks.cleanup_expired_manager_sessions.run()

    assert result == {"deleted": 1}
