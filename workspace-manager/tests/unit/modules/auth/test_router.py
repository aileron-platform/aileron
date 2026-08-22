"""HTTP behavior tests for Manager session bootstrap and logout."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from sqlalchemy import event

from app.modules.auth.oidc_core import LoginCompletion, LoginStart
from app.modules.auth.session import IssuedManagerSession, ManagerSessionService
from tests.helpers.manager_session import csrf_token_for_handle, find_session_for_handle


@contextmanager
def _captured_sql(session_factory) -> Iterator[list[str]]:
    statements: list[str] = []
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

    event.listen(engine, "before_cursor_execute", capture_statement)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", capture_statement)


def test_login_uses_browser_attempt_cookie_instead_of_ingress_peer(
    test_app,
    monkeypatch,
) -> None:
    client, _ = test_app
    begin_login = AsyncMock(
        return_value=LoginStart(
            authorization_url="https://issuer.example.com/authorize",
            state="state-1",
            attempt=Mock(),
        )
    )
    monkeypatch.setattr("app.modules.auth.router.OIDCCore.begin_login", begin_login)

    first = client.get("/api/v1/oauth2/login", follow_redirects=False)
    client.get("/api/v1/oauth2/login", follow_redirects=False)

    assert first.status_code == 302
    assert "aileron_login_attempt=" in first.headers["set-cookie"]
    assert "Path=/api/v1" in first.headers["set-cookie"]
    first_bucket = begin_login.await_args_list[0].kwargs["attempt_bucket"]
    second_bucket = begin_login.await_args_list[1].kwargs["attempt_bucket"]
    assert len(first_bucket) >= 32
    assert second_bucket == first_bucket


def test_session_bootstrap_returns_stable_csrf_across_tabs(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="admin",
        role_status="valid",
    )
    monkeypatch.setattr("app.modules.auth.middleware.SessionLocal", session_factory)
    with session_factory() as db:
        service = ManagerSessionService(db)
        issued = service.create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
    client.cookies.set("aileron_session", issued.handle)

    first_response = client.get("/api/v1/oauth2/session")
    second_response = client.get("/api/v1/oauth2/session")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    payload = first_response.json()
    assert payload["user"]["id"] == user.id
    assert payload["user"]["subject"] == user.oidc_subject
    assert payload["user"]["platform_role"] == "admin"
    assert "platform_resources.read" in payload["user"]["allowed_operations"]
    assert len(payload["csrf_token"]) >= 43
    assert second_response.json()["csrf_token"] == payload["csrf_token"]
    assert "provider" not in str(payload).lower()


def test_session_bootstrap_http_boundary_uses_one_select_and_no_write(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    monkeypatch.setattr("app.modules.auth.middleware.SessionLocal", session_factory)
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
    client.cookies.set("aileron_session", issued.handle)

    with _captured_sql(session_factory) as statements:
        response = client.get("/api/v1/oauth2/session")

    assert response.status_code == 200
    assert len([sql for sql in statements if sql.startswith("SELECT")]) == 1
    assert not any(sql.startswith(("UPDATE", "INSERT", "DELETE")) for sql in statements)


def test_session_rejection_uses_localized_envelope_and_correlation_id(test_app) -> None:
    client, _ = test_app
    correlation_id = "11111111-1111-4111-8111-111111111111"

    response = client.get(
        "/api/v1/oauth2/session",
        headers={
            "Accept-Language": "zh-TW",
            "X-Language": "zh-TW",
            "X-Correlation-ID": correlation_id,
        },
    )

    assert response.status_code == 401
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.json() == {
        "detail": {
            "errorCode": "MANAGER_SESSION_REQUIRED",
            "message": "需要 Manager Session 認證",
            "details": {},
        }
    }


def test_callback_redirects_to_validated_frontend_origin(
    test_app,
    monkeypatch,
) -> None:
    client, _ = test_app
    completion = LoginCompletion(
        user=SimpleNamespace(),
        session=IssuedManagerSession(
            handle="opaque-session-handle",
            absolute_expires_at=SimpleNamespace(),
        ),
        return_path="/workspaces?tab=active",
    )
    monkeypatch.setattr(
        "app.modules.auth.router.OIDCCore.complete_callback",
        AsyncMock(return_value=completion),
    )

    response = client.get(
        "/api/v1/oauth2/callback?code=code-1&state=state-1",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "https://aileron.test/workspaces?tab=active"
    )
    cookies = response.headers.get_list("set-cookie")
    assert any(
        "aileron_session=opaque-session-handle" in cookie and "Path=/api/v1" in cookie
        for cookie in cookies
    )
    assert any(
        "aileron_workspace_gateway_session=opaque-session-handle" in cookie
        and "Path=/workspaces" in cookie
        and "SameSite=none" in cookie
        and "Secure" in cookie
        for cookie in cookies
    )
    assert any(
        cookie.startswith("aileron_session=")
        and "Max-Age=0" in cookie
        and "Path=/" in cookie
        for cookie in cookies
    )
    assert any(
        cookie.startswith("aileron_workspace_gateway_session=")
        and "Max-Age=0" in cookie
        and "Path=/" in cookie
        for cookie in cookies
    )


def test_callback_issues_sandbox_compatible_workspace_gateway_cookie_for_loopback_http(
    test_app,
    monkeypatch,
) -> None:
    client, _ = test_app
    completion = LoginCompletion(
        user=SimpleNamespace(),
        session=IssuedManagerSession(
            handle="opaque-session-handle",
            absolute_expires_at=SimpleNamespace(),
        ),
        return_path="/workspaces",
    )
    monkeypatch.setattr(
        "app.modules.auth.router.OIDCCore.complete_callback",
        AsyncMock(return_value=completion),
    )
    monkeypatch.setattr(
        "app.modules.auth.router.get_settings",
        lambda: SimpleNamespace(PLATFORM_PUBLIC_ORIGIN="http://127.0.0.1:8082"),
    )

    response = client.get(
        "/api/v1/oauth2/callback?code=code-1&state=state-1",
        follow_redirects=False,
    )

    assert response.status_code == 303
    gateway_cookie = next(
        cookie
        for cookie in response.headers.get_list("set-cookie")
        if cookie.startswith("aileron_workspace_gateway_session=opaque-session-handle")
    )
    assert "Path=/workspaces" in gateway_cookie
    assert "SameSite=none" in gateway_cookie
    assert "Secure" in gateway_cookie


def test_cors_preflight_accepts_frontend_language_header(test_app) -> None:
    client, _ = test_app

    response = client.options(
        "/api/v1/oauth2/session",
        headers={
            "Origin": "https://aileron.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Language",
        },
    )

    assert response.status_code == 200
    assert "x-language" in response.headers["access-control-allow-headers"].lower()


def test_logout_is_post_and_revokes_local_session(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    monkeypatch.setattr("app.modules.auth.middleware.SessionLocal", session_factory)
    monkeypatch.setattr(
        "app.modules.auth.router.OIDCCore.provider_logout_url",
        AsyncMock(return_value=None),
    )
    with session_factory() as db:
        service = ManagerSessionService(db)
        issued = service.create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        csrf = csrf_token_for_handle(db, issued.handle)
    client.cookies.set("aileron_session", issued.handle)

    assert client.get("/api/v1/oauth2/logout").status_code == 405
    response = client.post(
        "/api/v1/oauth2/logout",
        headers={"Origin": "https://aileron.test", "X-CSRF-Token": csrf},
    )

    assert response.status_code == 200
    assert response.json() == {"provider_logout_url": None}
    cookies = response.headers.get_list("set-cookie")
    assert any(
        "aileron_session=" in cookie and "Path=/api/v1" in cookie for cookie in cookies
    )
    assert any(
        "aileron_workspace_gateway_session=" in cookie
        and "Path=/workspaces" in cookie
        and "SameSite=none" in cookie
        and "Secure" in cookie
        for cookie in cookies
    )
    with session_factory() as db:
        assert find_session_for_handle(db, issued.handle) is None


def test_logout_clears_sandbox_compatible_workspace_gateway_cookie_for_loopback_http(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )
    monkeypatch.setattr("app.modules.auth.middleware.SessionLocal", session_factory)
    monkeypatch.setattr(
        "app.modules.auth.router.OIDCCore.provider_logout_url",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.modules.auth.router.get_settings",
        lambda: SimpleNamespace(PLATFORM_PUBLIC_ORIGIN="http://127.0.0.1:8082"),
    )
    with session_factory() as db:
        issued = ManagerSessionService(db).create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        csrf = csrf_token_for_handle(db, issued.handle)
    client.cookies.set("aileron_session", issued.handle)

    response = client.post(
        "/api/v1/oauth2/logout",
        headers={"Origin": "https://aileron.test", "X-CSRF-Token": csrf},
    )

    assert response.status_code == 200
    gateway_cookie = next(
        cookie
        for cookie in response.headers.get_list("set-cookie")
        if cookie.startswith("aileron_workspace_gateway_session=")
    )
    assert "Max-Age=0" in gateway_cookie
    assert "Path=/workspaces" in gateway_cookie
    assert "SameSite=none" in gateway_cookie
    assert "Secure" in gateway_cookie
