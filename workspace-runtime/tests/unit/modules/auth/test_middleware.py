from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.auth import AuthenticationMiddleware, get_current_user_id
from app.modules.auth.execution_grant import (
    ExecutionGrantConflict,
    ExecutionGrantInvalid,
)


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthenticationMiddleware)

    @app.get("/api/v1/files/tree")
    async def secure(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "user_id": request.state.user_id,
                "actions": request.state.execution_grant.actions,
            }
        )

    @app.get("/api/v1/files/not-registered")
    async def unregistered_file_route() -> dict[str, bool]:
        return {"upstream": True}

    @app.get("/api/v1/client-browser-relay/health")
    async def browser_relay_health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/threads/thread-a/submit")
    async def submit_thread() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/internal/health")
    async def internal_health() -> dict[str, bool]:
        return {"ok": True}

    return app


def allow_grants(monkeypatch) -> Mock:
    verifier = Mock()
    verifier.verify.return_value = SimpleNamespace(
        subject="user-456", actions=("runtime_read",)
    )
    monkeypatch.setattr(
        "app.middleware.auth.get_execution_grant_verifier", lambda: verifier
    )
    return verifier


def test_get_current_user_id_returns_request_state_user_id() -> None:
    request = SimpleNamespace(state=SimpleNamespace(user_id="user-123"))

    assert get_current_user_id(request) == "user-123"


def test_public_and_internal_paths_bypass_execution_grants() -> None:
    client = TestClient(create_app())

    assert client.get("/api/v1/client-browser-relay/health").status_code == 200
    assert client.get("/api/v1/internal/health").status_code == 200


def test_missing_execution_grant_returns_401() -> None:
    response = TestClient(create_app()).get("/api/v1/files/tree")

    assert response.status_code == 401
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_EXECUTION_GRANT_MISSING"
    )
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_valid_grant_sets_request_identity_and_route_action(monkeypatch) -> None:
    verifier = allow_grants(monkeypatch)

    response = TestClient(create_app()).get(
        "/api/v1/files/tree", headers={"Authorization": "Bearer signed-grant"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-456",
        "actions": ["runtime_read"],
    }
    verifier.verify.assert_called_once_with("signed-grant", action="runtime_read")


def test_agent_route_requires_agent_action(monkeypatch) -> None:
    verifier = allow_grants(monkeypatch)

    response = TestClient(create_app()).post(
        "/api/v1/threads/thread-a/submit",
        headers={"Authorization": "Bearer signed-grant"},
    )

    assert response.status_code == 200
    verifier.verify.assert_called_once_with("signed-grant", action="agent")


def test_unknown_route_fails_closed_before_grant_verification(monkeypatch) -> None:
    verifier = allow_grants(monkeypatch)

    response = TestClient(create_app()).get(
        "/api/v1/files/not-registered",
        headers={"Authorization": "Bearer signed-grant", "X-Language": "en"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
    )
    verifier.verify.assert_not_called()


def test_instance_or_revision_conflict_returns_423(monkeypatch) -> None:
    verifier = allow_grants(monkeypatch)
    verifier.verify.side_effect = ExecutionGrantConflict(
        "WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH"
    )

    response = TestClient(create_app()).get(
        "/api/v1/files/tree",
        headers={"Authorization": "Bearer stale-grant", "X-Language": "en"},
    )

    assert response.status_code == 423
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH"
    )


def test_invalid_or_expired_grant_returns_401(monkeypatch) -> None:
    verifier = allow_grants(monkeypatch)
    verifier.verify.side_effect = ExecutionGrantInvalid(
        "WORKSPACE_EXECUTION_GRANT_EXPIRED"
    )

    response = TestClient(create_app()).get(
        "/api/v1/files/tree",
        headers={"Authorization": "Bearer expired-grant"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_EXECUTION_GRANT_EXPIRED"
    )


def test_shared_internal_token_cannot_bypass_execution_grant() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/files/tree", headers={"X-Internal-Token": "internal-secret"}
    )

    assert response.status_code == 401
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_EXECUTION_GRANT_MISSING"
    )
