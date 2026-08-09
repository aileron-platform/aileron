"""Public authorization contract and fixed-policy tests."""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from app import main as manager_main
from app.db import models as db_models
from app.modules.authorization.actor import actor_from_valid_user
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import (
    OPERATION_REQUIREMENTS,
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
    allowed_platform_operations,
    allowed_workspace_operations,
    operation_requirements_payload,
)
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSource,
    highest_role,
    normalize_resource_role,
    role_satisfies,
)
from app.modules.identity.platform_role import PLATFORM_ROLES, PlatformRole
from app.modules.knowledge_base.router import router as knowledge_base_router
from app.modules.marketplace.request import (
    MARKETPLACE_OPERATION_IDS,
    MarketplaceRequest,
)
from app.modules.workspace.access_repository import WorkspaceAccessResolver
from app.modules.workspace.router import router as workspace_router
from app.modules.workspace.setup_router import router as workspace_setup_router

CONTRACT_ROOT = Path("/repo-root/contracts/authorization")
REGISTERED_MANAGER_ROUTERS = (
    ("health", "", manager_main.health_router),
    ("oauth", "/api/v1", manager_main.oauth_router),
    ("admin_users", "/api/v1", manager_main.admin_users_router),
    ("platform_resources", "/api/v1", manager_main.platform_resources_router),
    (
        "platform_resource_analytics",
        "/api/v1",
        manager_main.platform_resource_analytics_router,
    ),
    (
        "platform_resource_capacity",
        "/api/v1",
        manager_main.platform_resource_capacity_router,
    ),
    ("user_groups", "/api/v1", manager_main.user_groups_router),
    ("users", "/api/v1", manager_main.users_router),
    ("workspaces", "/api/v1", manager_main.workspaces_router),
    ("knowledge_bases", "/api/v1", manager_main.knowledge_bases_router),
    ("marketplace", "/api/v1", manager_main.marketplace_router),
    ("workspace_setup", "/api/v1", manager_main.workspace_setup_router),
    ("settings", "/api/v1", manager_main.settings_router),
    ("automation", "/api/v1", manager_main.automation_router),
    (
        "internal_automation",
        "/api/v1",
        manager_main.internal_automation_router,
    ),
    (
        "internal_platform_resource_analytics",
        "/api/v1",
        manager_main.internal_platform_resource_analytics_router,
    ),
    ("container_images", "/api/v1", manager_main.container_images_router),
    ("oidc_auth", "/api/v1", manager_main.oidc_auth_router),
)

RUNTIME_ACCESS_OPERATIONS = frozenset(
    {
        OperationId.WORKSPACE_DETAIL_READ,
        OperationId.WORKSPACE_CONTENT_WRITE,
        OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        OperationId.WORKSPACE_TERMINAL_USE,
        OperationId.WORKSPACE_AGENT_CHAT_USE,
        OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
    }
)
DELEGATED_AUTHORIZATION_METHODS = {
    "require_read": OperationId.WORKSPACE_DETAIL_READ,
    "require_execute": OperationId.WORKSPACE_AUTOMATION_EXECUTE,
}
COMPOSITE_DELEGATED_AUTHORIZATION_METHODS = {
    "require_knowledge_base_mount": frozenset(
        {
            OperationId.WORKSPACE_ATTACHMENT_WRITE,
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        }
    ),
}

DYNAMIC_OPERATION_ROUTE_REQUIREMENTS = {
    (
        "workspaces",
        "create_workspace_execution_grant",
    ): RUNTIME_ACCESS_OPERATIONS,
    ("workspaces", "get_workspace_availability"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
            OperationId.WORKSPACE_DELETE,
            OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
        }
    ),
    ("workspaces", "request_workspace_availability_action"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
            OperationId.WORKSPACE_DELETE,
            OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
        }
    ),
    ("settings", "update_settings"): frozenset(
        {
            OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        }
    ),
    ("settings", "sync_settings_to_workspaces"): frozenset(
        {
            OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        }
    ),
    ("settings", "get_codex_login_status"): frozenset(
        {
            OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        }
    ),
    ("settings", "logout_codex"): frozenset(
        {
            OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        }
    ),
    ("marketplace", "install_marketplace_plugin"): frozenset(
        {
            OperationId.MARKETPLACE_INSTALL_EXECUTE,
        }
    ),
    ("marketplace", "preflight_marketplace_user_copy"): frozenset(
        {
            OperationId.MARKETPLACE_USER_COPY_MANAGE,
        }
    ),
    ("marketplace", "create_marketplace_user_copy"): frozenset(
        {
            OperationId.MARKETPLACE_USER_COPY_MANAGE,
        }
    ),
    ("automation", "create_job"): frozenset(
        {
            OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        }
    ),
    ("automation", "list_jobs"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
        }
    ),
    ("automation", "get_job"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
        }
    ),
    ("automation", "update_job"): frozenset(
        {
            OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        }
    ),
    ("automation", "pause_job"): frozenset(
        {
            OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        }
    ),
    ("automation", "resume_job"): frozenset(
        {
            OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        }
    ),
    ("automation", "delete_job"): frozenset(
        {
            OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        }
    ),
    ("automation", "run_job"): frozenset(
        {
            OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        }
    ),
    ("automation", "list_job_executions"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
        }
    ),
    ("automation", "list_executions"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
        }
    ),
    ("automation", "get_execution"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
        }
    ),
    ("automation", "cancel_execution"): frozenset(
        {
            OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        }
    ),
    ("automation", "get_metrics"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
        }
    ),
    ("automation", "get_calendar"): frozenset(
        {
            OperationId.WORKSPACE_DETAIL_READ,
        }
    ),
}

COMPOSITE_OPERATION_ROUTE_REQUIREMENTS = {
    (
        "knowledge_bases",
        "update_knowledge_base_visibility",
    ): frozenset(
        {
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            OperationId.KNOWLEDGE_BASE_VISIBILITY_MANAGE,
        }
    ),
    ("workspaces", "create_workspace_knowledge_base_attachment"): frozenset(
        {
            OperationId.WORKSPACE_ATTACHMENT_WRITE,
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        }
    ),
    (
        "knowledge_bases",
        "restore_knowledge_base_file_history",
    ): frozenset(
        {
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        }
    ),
    (
        "knowledge_bases",
        "enable_knowledge_base_git_repository",
    ): frozenset(
        {
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        }
    ),
    (
        "knowledge_bases",
        "clone_knowledge_base_git_repository",
    ): frozenset(
        {
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        }
    ),
}

NON_OPERATION_ROUTE_EXCEPTIONS = {
    ("health", "health_check"): "unauthenticated health endpoint",
    ("health", "oidc_health_check"): "unauthenticated health endpoint",
    ("oauth", "get_oauth_info"): "OAuth account self-service",
    ("oauth", "exchange_oauth_code"): "OAuth account self-service",
    ("oauth", "authenticate_and_save"): "OAuth account self-service",
    ("oauth", "refresh_oauth_token"): "OAuth account self-service",
    ("oauth", "oauth_health_check"): "OAuth provider health endpoint",
    ("users", "list_users"): "authenticated user directory",
    ("users", "get_user_profile"): "user profile self-service",
    ("settings", "get_settings"): "user settings self-service",
    ("settings", "start_codex_login"): "Codex login self-service",
    ("settings", "cancel_codex_login"): "Codex login self-service",
    ("settings", "generate_ssh_keys"): "SSH key self-service",
    (
        "internal_automation",
        "claim_execution",
    ): "Runtime-to-Manager internal callback",
    (
        "internal_automation",
        "complete_execution",
    ): "Runtime-to-Manager internal callback",
    (
        "internal_automation",
        "reconcile_restart",
    ): "Runtime-to-Manager internal callback",
    (
        "internal_platform_resource_analytics",
        "ingest_runtime_resource_telemetry",
    ): "Runtime control token authenticated telemetry callback",
    ("automation", "run_webhook"): "webhook secret authenticated execution",
    ("oidc_auth", "login"): "OIDC login lifecycle endpoint",
    ("oidc_auth", "callback"): "OIDC login lifecycle endpoint",
    ("oidc_auth", "session_bootstrap"): "Manager session self-service",
    ("oidc_auth", "logout"): "Manager session self-service",
}


@pytest.mark.parametrize(
    "manager_router",
    (
        workspace_router,
        workspace_setup_router,
        knowledge_base_router,
    ),
)
def test_every_manager_route_uses_request_scoped_authorization_actor(
    manager_router,
) -> None:
    routes = [route for route in manager_router.routes if isinstance(route, APIRoute)]

    assert routes
    assert len({(route.path, frozenset(route.methods)) for route in routes}) == len(
        routes
    )
    for route in routes:
        assert "actor" in inspect.signature(route.endpoint).parameters, route.name
        dependency_calls = {
            dependency.call
            for dependency in route.dependant.dependencies
            for dependency in (dependency, *dependency.dependencies)
        }
        assert get_authorization_actor in dependency_calls, route.name


def _operation_ids_in_callable(
    callable_object,
    seen: set[object] | None = None,
) -> set[OperationId]:
    seen = seen or set()
    if callable_object in seen:
        return set()
    seen.add(callable_object)
    tree = ast.parse(textwrap.dedent(inspect.getsource(callable_object)))
    operation_ids = {
        OperationId[node.attr]
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "OperationId"
        and node.attr in OperationId.__members__
    }
    module = inspect.getmodule(callable_object)
    if module is None:
        return operation_ids
    for call in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ):
        target = getattr(module, call.func.id, None)
        if (
            inspect.isfunction(target)
            and target.__module__ == callable_object.__module__
        ):
            operation_ids.update(_operation_ids_in_callable(target, seen))
    return operation_ids


def _operation_ids_in_service_method(
    service_type: type,
    method_name: str,
    seen: set[tuple[type, str]] | None = None,
) -> set[OperationId]:
    seen = seen or set()
    service_method_key = (service_type, method_name)
    if service_method_key in seen:
        return set()
    seen.add(service_method_key)
    service_method = getattr(service_type, method_name, None)
    if service_method is None:
        return set()
    operation_ids = _operation_ids_in_callable(service_method)
    tree = ast.parse(textwrap.dedent(inspect.getsource(service_method)))
    operation_ids.update(
        MARKETPLACE_OPERATION_IDS[node.func.attr]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in MARKETPLACE_OPERATION_IDS
    )
    operation_ids.update(
        DELEGATED_AUTHORIZATION_METHODS[node.func.attr]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in DELEGATED_AUTHORIZATION_METHODS
    )
    for call in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in COMPOSITE_DELEGATED_AUTHORIZATION_METHODS
    ):
        operation_ids.update(COMPOSITE_DELEGATED_AUTHORIZATION_METHODS[call.func.attr])
    initializer = service_type.__dict__.get("__init__")
    attribute_types: dict[str, type] = {}
    if inspect.isfunction(initializer):
        try:
            initializer_annotations = inspect.get_annotations(
                initializer,
                eval_str=True,
            )
        except NameError:
            initializer_annotations = {}
        initializer_tree = ast.parse(textwrap.dedent(inspect.getsource(initializer)))
        for assignment in (
            node
            for node in ast.walk(initializer_tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "self"
            and isinstance(node.value, ast.Name)
        ):
            attribute_type = initializer_annotations.get(assignment.value.id)
            if isinstance(attribute_type, type):
                attribute_types[assignment.targets[0].attr] = attribute_type
    for call in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    ):
        operation_ids.update(
            _operation_ids_in_service_method(
                service_type,
                call.func.attr,
                seen,
            )
        )
    for call in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "self"
    ):
        collaborator_type = attribute_types.get(call.func.value.attr)
        if collaborator_type is not None:
            operation_ids.update(
                _operation_ids_in_service_method(
                    collaborator_type,
                    call.func.attr,
                    seen,
                )
            )
    return operation_ids


def _operation_ids_in_dependencies(route: APIRoute) -> set[OperationId]:
    operation_ids: set[OperationId] = set()
    pending = list(route.dependant.dependencies)
    seen: set[object] = set()
    while pending:
        dependency = pending.pop()
        pending.extend(dependency.dependencies)
        dependency_call = dependency.call
        if dependency_call is None or dependency_call in seen:
            continue
        seen.add(dependency_call)
        operation_ids.update(_operation_ids_in_callable(dependency_call))
    return operation_ids


def _marketplace_operation_ids(endpoint) -> set[OperationId]:
    annotations = inspect.get_annotations(endpoint, eval_str=True)
    tree = ast.parse(textwrap.dedent(inspect.getsource(endpoint)))
    operation_ids: set[OperationId] = set()
    for attribute in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and annotations.get(node.value.id) is MarketplaceRequest
    ):
        operation_id = MARKETPLACE_OPERATION_IDS.get(attribute.attr)
        assert operation_id is not None, (
            endpoint.__name__,
            attribute.attr,
        )
        operation_ids.add(operation_id)
    return operation_ids


def _statically_reachable_operation_ids(route: APIRoute) -> set[OperationId]:
    endpoint = route.endpoint
    operation_ids = _operation_ids_in_callable(endpoint)
    operation_ids.update(_operation_ids_in_dependencies(route))
    operation_ids.update(_marketplace_operation_ids(endpoint))
    annotations = inspect.get_annotations(endpoint, eval_str=True)
    tree = ast.parse(textwrap.dedent(inspect.getsource(endpoint)))
    for call in (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
    ):
        service_type = annotations.get(call.func.value.id)
        if isinstance(service_type, type) and service_type.__module__.startswith(
            "app."
        ):
            operation_ids.update(
                _operation_ids_in_service_method(
                    service_type,
                    call.func.attr,
                )
            )
    return operation_ids


def test_main_registers_the_exhaustive_manager_router_inventory() -> None:
    registered = []
    for route in manager_main.app.routes:
        original_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if original_router is None or include_context is None:
            continue
        registered.append((include_context.prefix, original_router))

    assert registered == [
        (prefix, router) for _label, prefix, router in REGISTERED_MANAGER_ROUTERS
    ]


def test_every_registered_manager_route_method_has_operation_or_exception() -> None:
    seen_routes: set[tuple[str, str]] = set()
    seen_route_methods: set[tuple[str, str, str]] = set()
    invalid_classifications: list[tuple[tuple[str, str, str], set[OperationId]]] = []

    for router_label, app_prefix, router in REGISTERED_MANAGER_ROUTERS:
        routes = [route for route in router.routes if isinstance(route, APIRoute)]
        for route in routes:
            route_key = (router_label, route.name)
            assert route_key not in seen_routes, route_key
            seen_routes.add(route_key)
            full_path = f"{app_prefix}{route.path}"
            for method in route.methods:
                route_method = (method, full_path, route.name)
                assert route_method not in seen_route_methods, route_method
                seen_route_methods.add(route_method)

            operation_ids = _statically_reachable_operation_ids(route)
            if expected := DYNAMIC_OPERATION_ROUTE_REQUIREMENTS.get(route_key):
                assert operation_ids == expected, (
                    route_method,
                    operation_ids,
                    expected,
                )
                continue
            if expected := COMPOSITE_OPERATION_ROUTE_REQUIREMENTS.get(route_key):
                assert operation_ids == expected, (
                    route_method,
                    operation_ids,
                    expected,
                )
                continue
            if exception_reason := NON_OPERATION_ROUTE_EXCEPTIONS.get(route_key):
                assert exception_reason.strip(), route_method
                assert not operation_ids, (route_method, operation_ids)
                continue
            if len(operation_ids) != 1:
                invalid_classifications.append((route_method, operation_ids))

    assert not invalid_classifications, "\n".join(
        f"{route_method}: {sorted(operation.value for operation in operation_ids)}"
        for route_method, operation_ids in invalid_classifications
    )
    assert set(DYNAMIC_OPERATION_ROUTE_REQUIREMENTS) <= seen_routes
    assert set(COMPOSITE_OPERATION_ROUTE_REQUIREMENTS) <= seen_routes
    assert set(NON_OPERATION_ROUTE_EXCEPTIONS) <= seen_routes


def test_wire_contract_is_the_exact_public_authorization_vocabulary() -> None:
    wire = json.loads((CONTRACT_ROOT / "wire-contract.json").read_text())

    assert wire["schemaVersion"] == 2
    assert set(wire) == {
        "schemaVersion",
        "platformRoles",
        "resourceAccessRoles",
        "resourceAccessSources",
        "operationIds",
        "errorCodes",
    }
    assert wire["platformRoles"] == [role.value for role in PlatformRole]
    assert set(wire["platformRoles"]) == {role.value for role in PLATFORM_ROLES}
    assert wire["resourceAccessRoles"] == [role.value for role in ResourceAccessRole]
    assert wire["resourceAccessSources"] == [
        source.value for source in ResourceAccessSource
    ]
    assert wire["operationIds"] == [operation.value for operation in OperationId]
    assert {
        "MANAGER_SESSION_REQUIRED",
        "MANAGER_SESSION_ORIGIN_INVALID",
        "MANAGER_SESSION_CSRF_INVALID",
    } <= set(wire["errorCodes"])
    assert "capabilities" not in wire


def test_operation_policy_rejects_cross_enum_values_with_matching_wire_ids() -> None:
    actor = actor_from_valid_user(
        type(
            "User",
            (),
            {
                "id": "admin-id",
                "platform_role": PlatformRole.ADMIN,
                "role_status": "valid",
                "role_issues": [],
                "is_active": True,
                "identity_enabled": True,
            },
        )()
    )
    policy = AuthorizationOperationPolicy(object())

    with pytest.raises(AuthorizationOperationError) as exc_info:
        policy.require_platform_operation(
            actor,
            ResourceAccessRole.MANAGER,  # type: ignore[arg-type]
        )

    assert exc_info.value.error_code == "PLATFORM_AUTHORIZATION_DENIED"
    assert (
        allowed_platform_operations(
            OperationId.USER_MANAGEMENT_MANAGE,  # type: ignore[arg-type]
        )
        == ()
    )


def test_operation_requirement_snapshot_is_generated_from_fixed_policy() -> None:
    committed = json.loads((CONTRACT_ROOT / "operation-requirements.json").read_text())

    assert committed == operation_requirements_payload()
    assert set(OPERATION_REQUIREMENTS) == set(OperationId)
    assert all(
        not hasattr(requirement, "capability")
        and isinstance(requirement.platform_admin_only, bool)
        for requirement in OPERATION_REQUIREMENTS.values()
    )


def test_resource_access_policy_normalizes_and_compares_one_shared_role_type() -> None:
    assert normalize_resource_role("reader") is ResourceAccessRole.READER
    assert normalize_resource_role("editor") is None
    assert normalize_resource_role("viewer") is None
    assert normalize_resource_role(None) is None
    assert role_satisfies(ResourceAccessRole.OWNER, ResourceAccessRole.MANAGER)
    assert not role_satisfies(ResourceAccessRole.READER, ResourceAccessRole.MANAGER)
    assert (
        highest_role(
            [
                ResourceAccessRole.READER,
                ResourceAccessRole.OWNER,
                ResourceAccessRole.MANAGER,
            ]
        )
        is ResourceAccessRole.OWNER
    )
    assert highest_role([]) is None


@pytest.mark.parametrize(
    ("user", "expected_error_code"),
    (
        (object(), "AUTHORIZATION_ACTOR_INVALID_USER_ID"),
        (
            type("UserWithoutRole", (), {"id": "user-1"})(),
            "AUTHORIZATION_ACTOR_INVALID_PLATFORM_ROLE",
        ),
    ),
)
def test_authorization_actor_rejects_invalid_snapshots_with_machine_error_codes(
    user: object,
    expected_error_code: str,
) -> None:
    with pytest.raises(ValueError, match=f"^{expected_error_code}$"):
        actor_from_valid_user(user)


def test_authorization_actor_carries_a_typed_platform_role() -> None:
    user = type(
        "ValidUser",
        (),
        {"id": "user-1", "platform_role": "member"},
    )()

    actor = actor_from_valid_user(user)

    assert actor.platform_role is PlatformRole.MEMBER


def test_workspace_access_resolver_has_one_public_resolution_interface() -> None:
    assert hasattr(WorkspaceAccessResolver, "resolve")
    assert not hasattr(WorkspaceAccessResolver, "resolve_role")


def test_allowed_operations_use_only_platform_or_resource_role() -> None:
    assert allowed_workspace_operations(ResourceAccessRole.READER) == (
        "workspace.detail.read",
        "workspace.firewall.read",
        "workspace.sensitive_settings.read",
    )
    assert allowed_workspace_operations(ResourceAccessRole.MANAGER) == (
        "workspace.detail.read",
        "workspace.content.write",
        "workspace.lifecycle.execute",
        "workspace.metadata.write",
        "workspace.access.manage",
        "workspace.attachment.write",
        "workspace.firewall.read",
        "workspace.firewall.manage",
        "workspace.sensitive_settings.read",
        "workspace.sensitive_settings.manage",
        "workspace.terminal.use",
        "workspace.agent_chat.use",
        "workspace.automation.execute",
        "workspace.browser_automation.use",
    )
    assert allowed_platform_operations(PlatformRole.MEMBER) == (
        "marketplace.catalog.read",
        "marketplace.install.execute",
        "marketplace.user_copy.manage",
        "workspace.collection.read",
        "workspace.create",
        "knowledge_base.collection.read",
        "knowledge_base.create",
    )


def test_workspace_operation_facade_uses_resource_role_and_admin_override(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        platform_role="member",
        role_status="valid",
    )
    reader = create_user(
        platform_role="member",
        role_status="valid",
    )
    outsider = create_user(
        platform_role="admin",
        role_status="valid",
    )
    workspace_id = f"workspace-{uuid4().hex[:8]}"
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner.id,
                name="Policy Workspace",
                runtime="universal",
                provisioner="docker",
                runtime_status="stopped",
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        session.add(
            db_models.WorkspaceShare(
                id=f"share-{uuid4().hex[:8]}",
                workspace_id=workspace_id,
                target_type="user",
                target_id=reader.id,
                granted_by_user_id=owner.id,
                role="reader",
            )
        )
        session.commit()

        policy = AuthorizationOperationPolicy(
            session,
            override_audit_writer=MagicMock(),
        )
        owner_actor = actor_from_valid_user(owner)
        reader_actor = actor_from_valid_user(reader)
        outsider_actor = actor_from_valid_user(outsider)
        owner_operations = policy.allowed_workspace_operations(
            owner_actor,
            workspace_id,
        )
        assert "workspace.delete" in owner_operations
        assert policy.allowed_workspace_operations(reader_actor, workspace_id) == (
            "workspace.detail.read",
            "workspace.firewall.read",
            "workspace.sensitive_settings.read",
        )
        owner_grant = policy.require_workspace_operation(
            owner_actor,
            workspace_id,
            OperationId.WORKSPACE_CONTENT_WRITE,
        )
        assert owner_grant.access_role is ResourceAccessRole.OWNER
        assert owner_grant.access_source is ResourceAccessSource.OWNED

        admin_grant = policy.require_workspace_operation(
            outsider_actor,
            workspace_id,
            OperationId.WORKSPACE_CONTENT_WRITE,
        )
        assert admin_grant.access_role is ResourceAccessRole.MANAGER
        assert admin_grant.access_source is ResourceAccessSource.PLATFORM_ADMIN
        assert admin_grant.access_sources == (ResourceAccessSource.PLATFORM_ADMIN,)
        assert "workspace.delete" not in policy.allowed_workspace_operations(
            outsider_actor,
            workspace_id,
        )
        with pytest.raises(AuthorizationOperationError) as denied:
            policy.require_workspace_operation(
                outsider_actor,
                workspace_id,
                OperationId.WORKSPACE_DELETE,
            )
        assert (denied.value.error_code, denied.value.http_status) == (
            "WORKSPACE_OPERATION_DENIED",
            403,
        )
