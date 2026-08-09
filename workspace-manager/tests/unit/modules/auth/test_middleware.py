"""HTTP behavior tests for Manager session and CSRF middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.modules.auth.middleware import ManagerSessionAuthenticationMiddleware
from app.modules.auth.session import ManagerSessionService
from tests.helpers.manager_session import csrf_token_for_handle


def _client(
    session_factory,
    monkeypatch,
    *,
    auth_session_closed: list[bool] | None = None,
) -> TestClient:
    app = FastAPI()
    app.add_middleware(ManagerSessionAuthenticationMiddleware)

    @app.get("/whoami")
    async def whoami(request: Request):
        return {"userId": getattr(request.state, "user_id", None)}

    @app.post("/mutation")
    async def mutation(request: Request):
        return {"userId": getattr(request.state, "user_id", None)}

    @app.get("/connection-state")
    async def connection_state(_request: Request):
        return {"authSessionClosed": auth_session_closed == [True]}

    monkeypatch.setattr("app.modules.auth.middleware.SessionLocal", session_factory)
    return TestClient(app, base_url="https://aileron.test")


def test_cookie_session_authenticates_safe_request(
    test_app, create_user, monkeypatch
) -> None:
    _, session_factory = test_app
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
    client = _client(session_factory, monkeypatch)
    client.cookies.set("aileron_session", issued.handle)

    assert client.get("/whoami").json() == {"userId": user.id}


def test_mutation_requires_exact_origin_and_current_csrf(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
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
    client = _client(session_factory, monkeypatch)
    client.cookies.set("aileron_session", issued.handle)

    wrong_origin = client.post(
        "/mutation",
        headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
    )
    missing_csrf = client.post(
        "/mutation",
        headers={"Origin": "https://aileron.test"},
    )
    accepted = client.post(
        "/mutation",
        headers={"Origin": "https://aileron.test", "X-CSRF-Token": csrf},
    )

    assert wrong_origin.status_code == 403
    assert (
        wrong_origin.json()["detail"]["errorCode"] == "MANAGER_SESSION_ORIGIN_INVALID"
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["detail"]["errorCode"] == "MANAGER_SESSION_CSRF_INVALID"
    assert accepted.status_code == 200


def test_provider_bearer_is_not_a_manager_session(test_app, monkeypatch) -> None:
    _, session_factory = test_app
    client = _client(session_factory, monkeypatch)

    response = client.get(
        "/whoami",
        headers={"Authorization": "Bearer provider-access-token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "errorCode": "MANAGER_SESSION_REQUIRED",
            "message": "auth.manager_session.required",
            "details": {},
        }
    }


def test_authentication_database_session_is_closed_before_route_execution(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
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

    closed: list[bool] = []

    class TrackingSessionContext:
        def __init__(self) -> None:
            self.db = session_factory()

        def __enter__(self):
            return self.db

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            self.db.close()
            closed.append(True)

    client = _client(
        TrackingSessionContext,
        monkeypatch,
        auth_session_closed=closed,
    )
    client.cookies.set("aileron_session", issued.handle)

    response = client.get("/connection-state")

    assert response.status_code == 200
    assert response.json() == {"authSessionClosed": True}
