"""Public seam tests for Manager request authentication."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread

import pytest
from sqlalchemy import event

from app.db import models as db_models
from app.modules.auth.request_authentication import (
    ManagerRequestAuthentication,
    ManagerRequestAuthenticationError,
    ManagerRequestEvidence,
)
from app.modules.auth.session import ManagerSessionService
from tests.helpers.manager_session import session_for_handle


@contextmanager
def _captured_sql(session_factory) -> Iterator[tuple[list[str], list[int]]]:
    statements: list[str] = []
    update_rowcounts: list[int] = []
    engine = session_factory.kw["bind"]

    def capture_statement(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        statements.append(statement.lstrip().upper())

    def capture_rowcount(
        _connection,
        cursor,
        statement: str,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        if statement.lstrip().upper().startswith("UPDATE"):
            update_rowcounts.append(cursor.rowcount)

    event.listen(engine, "before_cursor_execute", capture_statement)
    event.listen(engine, "after_cursor_execute", capture_rowcount)
    try:
        yield statements, update_rowcounts
    finally:
        event.remove(engine, "before_cursor_execute", capture_statement)
        event.remove(engine, "after_cursor_execute", capture_rowcount)


def _authenticate(
    session_factory,
    *,
    handle: str | None,
    now: datetime | None = None,
    method: str = "GET",
    origin: str | None = None,
    csrf_token: str | None = None,
) -> None:
    ManagerRequestAuthentication(
        session_factory=session_factory,
        platform_public_origin="https://aileron.test",
        clock=(lambda: now) if now is not None else None,
    ).authenticate(
        ManagerRequestEvidence(
            session_handle=handle,
            method=method,
            origin=origin,
            csrf_token=csrf_token,
        )
    )


def _assert_sql_budget(
    statements: list[str],
    *,
    selects: int,
    writes: int,
) -> None:
    assert len([sql for sql in statements if sql.startswith("SELECT")]) == selects
    assert (
        len(
            [
                sql
                for sql in statements
                if sql.startswith(("UPDATE", "INSERT", "DELETE"))
            ]
        )
        == writes
    )


def test_authenticate_builds_immutable_context_with_one_select_and_no_write(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    user = create_user(
        id="local-user-1",
        username="nova",
        email="nova@example.com",
        display_name="Nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer="https://oidc.test.example",
            subject=user.oidc_subject,
            authentication_context={},
        )

    with _captured_sql(session_factory) as (statements, _update_rowcounts):
        authenticated = ManagerRequestAuthentication(
            session_factory=session_factory,
            platform_public_origin="https://aileron.test",
        ).authenticate(
            ManagerRequestEvidence(
                session_handle=issued.handle,
                method="GET",
                origin=None,
                csrf_token=None,
            )
        )
    assert authenticated.session_id
    assert authenticated.user.id == user.id
    assert authenticated.user.username == "nova"
    assert authenticated.actor.user_id == user.id
    assert authenticated.actor.platform_role.value == "member"
    _assert_sql_budget(statements, selects=1, writes=0)

    try:
        authenticated.session_id = "replacement"
    except (AttributeError, TypeError):
        pass
    else:  # pragma: no cover - Documents the immutable public contract.
        raise AssertionError("AuthenticatedManagerRequest must be immutable")


@pytest.mark.parametrize(
    ("handle", "expected_selects"),
    [(None, 0), ("", 0), ("unknown-session", 1)],
    ids=["missing", "empty", "unknown"],
)
def test_missing_or_unknown_session_returns_401_with_bounded_sql(
    test_app,
    handle: str | None,
    expected_selects: int,
) -> None:
    _, session_factory = test_app

    with _captured_sql(session_factory) as (statements, _update_rowcounts):
        with pytest.raises(ManagerRequestAuthenticationError) as rejected:
            _authenticate(session_factory, handle=handle)

    assert rejected.value.status_code == 401
    assert rejected.value.error_code == "MANAGER_SESSION_REQUIRED"
    _assert_sql_budget(statements, selects=expected_selects, writes=0)


@pytest.mark.parametrize(
    "invalid_state", ["idle_expired", "absolute_expired", "principal_mismatch"]
)
def test_invalid_session_evidence_returns_401_without_request_path_cleanup(
    test_app,
    create_user,
    invalid_state: str,
) -> None:
    _, session_factory = test_app
    now = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        stored = session_for_handle(db, issued.handle)
        stored.last_activity_at = now - timedelta(minutes=1)
        stored.idle_expires_at = now + timedelta(minutes=10)
        stored.absolute_expires_at = now + timedelta(hours=1)
        if invalid_state == "idle_expired":
            stored.idle_expires_at = now
        elif invalid_state == "absolute_expired":
            stored.absolute_expires_at = now
        else:
            stored.oidc_subject = "different-subject"
        session_id = stored.id
        db.commit()

    with _captured_sql(session_factory) as (statements, _update_rowcounts):
        with pytest.raises(ManagerRequestAuthenticationError) as rejected:
            _authenticate(session_factory, handle=issued.handle, now=now)

    assert rejected.value.status_code == 401
    assert rejected.value.error_code == "MANAGER_SESSION_REQUIRED"
    _assert_sql_budget(statements, selects=1, writes=0)
    with session_factory() as db:
        assert db.get(db_models.ManagerSession, session_id) is not None


@pytest.mark.parametrize(
    "user_overrides",
    [
        {"is_active": False},
        {"identity_enabled": False},
        {"sync_status": "local_shadow_missing"},
        {"role_status": "multiple"},
        {"platform_role": None},
        {"role_issues": ["unexpected_issue"]},
    ],
    ids=[
        "inactive",
        "identity-disabled",
        "sync-invalid",
        "role-status-invalid",
        "platform-role-invalid",
        "role-issues-inconsistent",
    ],
)
def test_local_authorization_denial_returns_403_and_preserves_session(
    test_app,
    create_user,
    user_overrides: dict[str, object],
) -> None:
    _, session_factory = test_app
    user_data: dict[str, object] = {
        "id": "local-user-1",
        "username": "nova",
        "platform_role": "member",
        "role_status": "valid",
    }
    user_data.update(user_overrides)
    user = create_user(
        **user_data,
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        session_id = session_for_handle(db, issued.handle).id

    with _captured_sql(session_factory) as (statements, _update_rowcounts):
        with pytest.raises(ManagerRequestAuthenticationError) as rejected:
            _authenticate(session_factory, handle=issued.handle)

    assert rejected.value.status_code == 403
    assert rejected.value.error_code == "PLATFORM_AUTHORIZATION_DENIED"
    _assert_sql_budget(statements, selects=1, writes=0)
    with session_factory() as db:
        assert db.get(db_models.ManagerSession, session_id) is not None


def test_valid_mutation_within_touch_window_uses_one_select_and_no_write(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    now = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        stored = session_for_handle(db, issued.handle)
        stored.last_activity_at = now - timedelta(seconds=30)
        stored.idle_expires_at = now + timedelta(minutes=10)
        stored.absolute_expires_at = now + timedelta(hours=1)
        csrf_token = stored.csrf_token
        db.commit()

    with _captured_sql(session_factory) as (statements, _update_rowcounts):
        _authenticate(
            session_factory,
            handle=issued.handle,
            now=now,
            method="POST",
            origin="https://aileron.test",
            csrf_token=csrf_token,
        )

    _assert_sql_budget(statements, selects=1, writes=0)


@pytest.mark.parametrize(
    ("origin", "csrf_mode", "expected_error_code"),
    [
        ("https://evil.example", "valid", "MANAGER_SESSION_ORIGIN_INVALID"),
        ("https://aileron.test", "invalid", "MANAGER_SESSION_CSRF_INVALID"),
    ],
    ids=["origin", "csrf"],
)
def test_mutation_security_rejection_uses_one_select_and_no_write(
    test_app,
    create_user,
    origin: str,
    csrf_mode: str,
    expected_error_code: str,
) -> None:
    _, session_factory = test_app
    now = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        stored = session_for_handle(db, issued.handle)
        stored.last_activity_at = now - timedelta(seconds=30)
        stored.idle_expires_at = now + timedelta(minutes=10)
        stored.absolute_expires_at = now + timedelta(hours=1)
        csrf_token = stored.csrf_token if csrf_mode == "valid" else "invalid-token"
        db.commit()

    with _captured_sql(session_factory) as (statements, _update_rowcounts):
        with pytest.raises(ManagerRequestAuthenticationError) as rejected:
            _authenticate(
                session_factory,
                handle=issued.handle,
                now=now,
                method="POST",
                origin=origin,
                csrf_token=csrf_token,
            )

    assert rejected.value.status_code == 403
    assert rejected.value.error_code == expected_error_code
    _assert_sql_budget(statements, selects=1, writes=0)


def test_touch_never_extends_absolute_expiry(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    now = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        stored = session_for_handle(db, issued.handle)
        stored.last_activity_at = now - timedelta(seconds=61)
        stored.idle_expires_at = now + timedelta(seconds=10)
        stored.absolute_expires_at = now + timedelta(seconds=30)
        absolute_expires_at = stored.absolute_expires_at
        db.commit()

    with _captured_sql(session_factory) as (statements, update_rowcounts):
        _authenticate(session_factory, handle=issued.handle, now=now)

    _assert_sql_budget(statements, selects=1, writes=1)
    assert update_rowcounts == [1]
    with session_factory() as db:
        stored = session_for_handle(db, issued.handle)
        assert (
            stored.absolute_expires_at.replace(tzinfo=timezone.utc)
            == absolute_expires_at
        )
        assert (
            stored.idle_expires_at.replace(tzinfo=timezone.utc) == absolute_expires_at
        )


def test_touch_preserves_session_specific_idle_timeout(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    now = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)
    idle_timeout = timedelta(minutes=5)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        issued = ManagerSessionService(db, idle_timeout=idle_timeout).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        stored = session_for_handle(db, issued.handle)
        stored.last_activity_at = now - timedelta(seconds=61)
        stored.idle_expires_at = stored.last_activity_at + idle_timeout
        stored.absolute_expires_at = now + timedelta(hours=1)
        db.commit()

    _authenticate(session_factory, handle=issued.handle, now=now)

    with session_factory() as db:
        stored = session_for_handle(db, issued.handle)
        assert stored.last_activity_at.replace(tzinfo=timezone.utc) == now
        assert stored.idle_expires_at.replace(tzinfo=timezone.utc) == now + idle_timeout


def test_two_stale_request_projections_conditionally_update_at_most_one_row(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    now = datetime(2026, 8, 8, 6, 30, tzinfo=timezone.utc)
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        stored = session_for_handle(db, issued.handle)
        stored.last_activity_at = now - timedelta(seconds=61)
        stored.idle_expires_at = now + timedelta(minutes=10)
        stored.absolute_expires_at = now + timedelta(hours=1)
        db.commit()

    original_touch = ManagerRequestAuthentication._touch_if_due
    both_loaded = Event()
    first_finished = Event()
    arrival_lock = Lock()
    arrivals = 0

    def coordinated_touch(self, db, *, projection, now):
        nonlocal arrivals
        with arrival_lock:
            arrivals += 1
            position = arrivals
            if arrivals == 2:
                both_loaded.set()
        assert both_loaded.wait(timeout=2)
        if position == 2:
            assert first_finished.wait(timeout=2)
        original_touch(self, db, projection=projection, now=now)
        if position == 1:
            first_finished.set()

    monkeypatch.setattr(
        ManagerRequestAuthentication,
        "_touch_if_due",
        coordinated_touch,
    )
    failures: list[BaseException] = []

    def authenticate_request() -> None:
        try:
            _authenticate(session_factory, handle=issued.handle, now=now)
        except BaseException as exc:  # pragma: no cover - surfaced below
            failures.append(exc)

    with _captured_sql(session_factory) as (statements, update_rowcounts):
        workers = [Thread(target=authenticate_request) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=5)

    assert not failures
    assert all(not worker.is_alive() for worker in workers)
    _assert_sql_budget(statements, selects=2, writes=2)
    assert sorted(update_rowcounts) == [0, 1]
