"""Admin platform-operation dependency tests."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

import app.modules.identity.admin_authorization as admin_authorization_module
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    OperationId,
)
from app.modules.identity.admin_authorization import require_admin_user
from app.modules.identity.admin_router import router as admin_user_router
from app.modules.identity.group_router import router as user_group_router


def _request() -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/"})
    request.state.translate = lambda key, **_params: f"translated:{key}"
    return request


def test_admin_dependency_uses_closed_user_management_operation(monkeypatch) -> None:
    db = MagicMock()
    user = MagicMock()
    db.get.return_value = user
    policy = MagicMock()
    monkeypatch.setattr(
        admin_authorization_module,
        "AuthorizationOperationPolicy",
        lambda _db: policy,
    )
    actor = AuthorizationActor(user_id="admin-1", platform_role="admin")

    result = require_admin_user(_request(), actor, db)

    assert result is user
    policy.require_platform_operation.assert_called_once_with(
        actor,
        OperationId.USER_MANAGEMENT_MANAGE,
    )


def test_admin_dependency_returns_structured_authorization_denial(monkeypatch) -> None:
    db = MagicMock()
    policy = MagicMock()
    policy.require_platform_operation.side_effect = AuthorizationOperationError(
        "PLATFORM_AUTHORIZATION_DENIED",
        403,
    )
    monkeypatch.setattr(
        admin_authorization_module,
        "AuthorizationOperationPolicy",
        lambda _db: policy,
    )

    with pytest.raises(HTTPException) as exc_info:
        require_admin_user(
            _request(),
            AuthorizationActor(
                user_id="read-only-1",
                platform_role="member",
            ),
            db,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "errorCode": "PLATFORM_AUTHORIZATION_DENIED",
        "message": "translated:access_denied",
        "details": {},
    }


def test_every_admin_route_uses_the_shared_user_management_gate() -> None:
    routes = [
        route
        for router in (admin_user_router, user_group_router)
        for route in router.routes
        if isinstance(route, APIRoute)
    ]

    assert routes
    for route in routes:
        dependency_calls = {
            dependency.call
            for dependency in route.dependant.dependencies
            for dependency in (dependency, *dependency.dependencies)
        }
        assert require_admin_user in dependency_calls, route.name
