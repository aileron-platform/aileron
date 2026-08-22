"""Marketplace request-boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

import app.modules.marketplace.request as marketplace_request_module
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    OperationId,
)
from app.modules.marketplace.request import MarketplaceRequest
from app.modules.marketplace.router import (
    get_marketplace_request,
    router as marketplace_router,
)
from app.modules.marketplace.workflows.package_reads import MarketplacePackageReadModel
from app.modules.marketplace.workflows.registry_operations import MarketplacePathError


def _request(*, auth_enabled: bool = True) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/"})
    request.state.auth_enabled = auth_enabled
    request.state.user_id = "user-1"
    request.state.translate = lambda key, **_params: f"translated:{key}"
    return request


def _actor(role: str = "member") -> AuthorizationActor:
    return AuthorizationActor(user_id="user-1", platform_role=role)


@pytest.mark.parametrize(
    "operation",
    [
        "list_packages",
        "create_package",
        "scan_import_source",
        "list_activity",
        "get_registry_status",
        "preflight_user_copy",
    ],
)
def test_request_dispatches_each_workflow_category(operation: str) -> None:
    marketplace = MarketplaceRequest.create()

    with pytest.raises(TypeError):
        marketplace.execute(operation)


def test_request_rejects_unknown_operation() -> None:
    marketplace = MarketplaceRequest.create()

    with pytest.raises(AttributeError, match="Marketplace operation is not available"):
        marketplace.execute("missing_operation")


@pytest.mark.parametrize(
    ("operation", "operation_id"),
    [
        ("list_packages", OperationId.MARKETPLACE_CATALOG_READ),
        ("get_package_operation_summary", OperationId.MARKETPLACE_CATALOG_READ),
        ("create_package", OperationId.MARKETPLACE_CONTENT_PUBLISH),
        ("delete_package", OperationId.MARKETPLACE_DELETE_EXECUTE),
        ("preflight_user_copy", OperationId.MARKETPLACE_USER_COPY_MANAGE),
        (
            "resolve_managed_package_for_install",
            OperationId.MARKETPLACE_INSTALL_EXECUTE,
        ),
        ("resolve_install_runtime", OperationId.MARKETPLACE_INSTALL_EXECUTE),
        ("get_settings", OperationId.MARKETPLACE_REGISTRY_MANAGE),
        ("get_registry_status", OperationId.MARKETPLACE_REGISTRY_MANAGE),
        ("initialize_git_repository", OperationId.MARKETPLACE_REGISTRY_MANAGE),
    ],
)
def test_request_authorizes_operation_before_dispatch(
    operation: str,
    operation_id: OperationId,
    monkeypatch,
) -> None:
    authorization = MagicMock()
    monkeypatch.setattr(
        marketplace_request_module,
        "AuthorizationOperationPolicy",
        lambda _db: authorization,
    )
    marketplace = MarketplaceRequest.create(
        MagicMock(),
        request=_request(),
        actor=_actor(),
    )

    with pytest.raises(TypeError):
        marketplace.execute(operation)

    authorization.require_platform_operation.assert_called_once_with(
        _actor(),
        operation_id,
    )


def test_request_translates_authorization_denial(monkeypatch) -> None:
    authorization = MagicMock()
    authorization.require_platform_operation.side_effect = AuthorizationOperationError(
        "PLATFORM_AUTHORIZATION_DENIED",
        403,
    )
    monkeypatch.setattr(
        marketplace_request_module,
        "AuthorizationOperationPolicy",
        lambda _db: authorization,
    )
    marketplace = MarketplaceRequest.create(
        MagicMock(),
        request=_request(),
        actor=_actor("member"),
    )

    with pytest.raises(HTTPException) as exc_info:
        marketplace.execute("create_package")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "errorCode": "PLATFORM_AUTHORIZATION_DENIED",
        "message": "translated:marketplace.permission.denied",
        "details": {},
    }


def test_authenticated_request_without_verified_actor_fails_closed(monkeypatch) -> None:
    authorization = MagicMock()
    authorization.require_platform_operation.side_effect = AuthorizationOperationError(
        "PLATFORM_AUTHORIZATION_DENIED", 401
    )
    monkeypatch.setattr(
        marketplace_request_module,
        "AuthorizationOperationPolicy",
        lambda _db: authorization,
    )
    marketplace = MarketplaceRequest.create(
        MagicMock(),
        request=_request(),
    )

    with pytest.raises(HTTPException) as exc_info:
        marketplace.execute("list_packages")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["errorCode"] == "PLATFORM_AUTHORIZATION_DENIED"


def test_every_exposed_marketplace_operation_has_one_closed_operation_id() -> None:
    marketplace = MarketplaceRequest.create()

    assert set(marketplace._operations) == set(  # noqa: SLF001
        marketplace_request_module.MARKETPLACE_OPERATION_IDS
    )
    assert all(
        isinstance(operation_id, OperationId)
        for operation_id in marketplace_request_module.MARKETPLACE_OPERATION_IDS.values()
    )


def test_every_registry_query_requires_registry_manage() -> None:
    registry_queries = {
        operation
        for operation in marketplace_request_module.MARKETPLACE_OPERATION_IDS
        if operation == "get_settings"
        or operation.startswith("get_registry_")
        or operation.startswith("list_registry_")
    }

    assert registry_queries
    assert {
        marketplace_request_module.MARKETPLACE_OPERATION_IDS[operation]
        for operation in registry_queries
    } == {OperationId.MARKETPLACE_REGISTRY_MANAGE}
    assert (
        marketplace_request_module.MARKETPLACE_OPERATION_IDS["list_activity"]
        is OperationId.MARKETPLACE_CATALOG_READ
    )


def test_every_marketplace_route_has_one_closed_operation_gate() -> None:
    source = Path("/workspace-manager/app/modules/marketplace/router.py").read_text()
    tree = ast.parse(source)
    routes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == "router"
            for decorator in node.decorator_list
        )
    }

    observed: dict[str, OperationId] = {}
    for route_name, route_node in routes.items():
        calls = {
            attribute.attr
            for attribute in ast.walk(route_node)
            if isinstance(attribute, ast.Attribute)
            and isinstance(attribute.value, ast.Name)
            and attribute.value.id == "service"
        }
        operation_ids = {
            marketplace_request_module.MARKETPLACE_OPERATION_IDS[call]
            for call in calls
            if call in marketplace_request_module.MARKETPLACE_OPERATION_IDS
        }
        if route_name == "install_marketplace_plugin":
            operation_ids.add(OperationId.MARKETPLACE_INSTALL_EXECUTE)
        if len(operation_ids) > 1:
            operation_ids.discard(OperationId.MARKETPLACE_CATALOG_READ)
        assert len(operation_ids) == 1, route_name
        observed[route_name] = operation_ids.pop()

    registered_routes = [
        route for route in marketplace_router.routes if isinstance(route, APIRoute)
    ]
    assert {route.name for route in registered_routes} == set(observed)
    for route in registered_routes:
        dependency_calls = {
            dependency.call
            for dependency in route.dependant.dependencies
            for dependency in (dependency, *dependency.dependencies)
        }
        assert get_marketplace_request in dependency_calls, route.name


def test_request_translates_workflow_error(monkeypatch) -> None:
    def reject_path(*_args, **_kwargs):
        raise MarketplacePathError("marketplace.resource.path_invalid")

    monkeypatch.setattr(MarketplacePackageReadModel, "read_package_file", reject_path)
    marketplace = MarketplaceRequest.create(request=_request(auth_enabled=False))

    with pytest.raises(HTTPException) as exc_info:
        marketplace.execute("read_package_file", "user-1", "codex", "package", "../x")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "translated:marketplace.resource.path_invalid"
