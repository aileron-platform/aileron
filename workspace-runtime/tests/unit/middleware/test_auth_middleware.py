from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.auth import AuthenticationMiddleware, get_current_user_id
from app.services.auth_service import SimpleUser


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthenticationMiddleware)

    @app.get("/secure")
    async def secure(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "user_id": request.state.user_id,
                "user": request.state.user.id,
            }
        )

    @app.get("/favicon.ico")
    async def favicon() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/internal/health")
    async def internal_health() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_get_current_user_id_returns_request_state_user_id() -> None:
    request = SimpleNamespace(state=SimpleNamespace(user_id="user-123"))

    assert get_current_user_id(request) == "user-123"


def test_public_path_bypasses_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_internal_api_prefix_bypasses_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/internal/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_missing_authorization_header_returns_401() -> None:
    client = TestClient(create_app())

    response = client.get("/secure")

    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "MISSING_AUTH_HEADER"
    assert body["detail"] == "Missing or invalid Authorization header"
    assert "timestamp" in body
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_valid_bearer_token_sets_request_state(monkeypatch) -> None:
    auth_service = AsyncMock()
    auth_service.validate_access_token.return_value = SimpleUser("user-456")
    monkeypatch.setattr("app.middleware.auth.get_auth_service", lambda: auth_service)

    client = TestClient(create_app())
    response = client.get("/secure", headers={"Authorization": "Bearer valid.jwt.token"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-456", "user": "user-456"}
    auth_service.validate_access_token.assert_awaited_once_with("valid.jwt.token")


def test_internal_token_authentication_sets_internal_test_user(monkeypatch) -> None:
    monkeypatch.setattr("app.middleware.auth.INTERNAL_API_TOKEN", "internal-secret")

    client = TestClient(create_app())
    response = client.get("/secure", headers={"X-Internal-Token": "internal-secret"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "internal-test-user",
        "user": "internal-test-user",
    }


def test_invalid_token_returns_token_expired_error(monkeypatch) -> None:
    auth_service = AsyncMock()
    auth_service.validate_access_token.return_value = None
    monkeypatch.setattr("app.middleware.auth.get_auth_service", lambda: auth_service)

    client = TestClient(create_app())
    response = client.get("/secure", headers={"Authorization": "Bearer invalid.jwt.token"})

    assert response.status_code == 401
    assert response.json()["error_code"] == "TOKEN_EXPIRED"
