"""Public seams for the simplified platform and resource authorization policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.authorization.actor import actor_from_valid_user
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OPERATION_REQUIREMENTS,
    OperationId,
    allowed_workspace_operations,
    operation_requirements_payload,
)
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    normalize_resource_role,
)

CONTRACT_ROOT = Path("/repo-root/contracts/authorization")


def _actor(role: str):
    return actor_from_valid_user(
        type(
            "UserSnapshot",
            (),
            {"id": f"{role}-id", "platform_role": role},
        )()
    )


def test_wire_contract_exposes_only_simplified_authorization_vocabulary() -> None:
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
    assert wire["platformRoles"] == ["admin", "member"]
    assert wire["resourceAccessRoles"] == ["reader", "manager", "owner"]
    assert wire["resourceAccessSources"] == [
        "owned",
        "direct_share",
        "group_share",
        "public",
        "platform_admin",
    ]
    assert "capabilities" not in wire


def test_operation_requirements_have_no_capability_dimension() -> None:
    committed = json.loads((CONTRACT_ROOT / "operation-requirements.json").read_text())

    assert committed == operation_requirements_payload()
    assert committed["schemaVersion"] == 2
    assert set(OPERATION_REQUIREMENTS) == set(OperationId)
    assert all(
        set(requirement)
        == {
            "operationId",
            "scope",
            "minimumResourceRole",
            "platformAdminOnly",
        }
        for requirement in committed["requirements"]
    )


def test_resource_role_policy_accepts_only_reader_manager_and_owner() -> None:
    assert {role.value for role in ResourceAccessRole} == {
        "reader",
        "manager",
        "owner",
    }
    assert normalize_resource_role("editor") is None


def test_allowed_operations_depend_only_on_resource_role() -> None:
    reader_operations = allowed_workspace_operations(ResourceAccessRole.READER)
    manager_operations = allowed_workspace_operations(ResourceAccessRole.MANAGER)
    owner_operations = allowed_workspace_operations(ResourceAccessRole.OWNER)

    assert reader_operations == (
        "workspace.detail.read",
        "workspace.firewall.read",
        "workspace.sensitive_settings.read",
    )
    assert "workspace.delete" not in manager_operations
    assert set(owner_operations) == {*manager_operations, "workspace.delete"}


@pytest.mark.parametrize(
    "operation",
    (
        OperationId.WORKSPACE_CONTENT_WRITE,
        OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
        OperationId.WORKSPACE_METADATA_WRITE,
        OperationId.WORKSPACE_ACCESS_MANAGE,
        OperationId.WORKSPACE_ATTACHMENT_WRITE,
        OperationId.WORKSPACE_FIREWALL_MANAGE,
        OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        OperationId.WORKSPACE_TERMINAL_USE,
        OperationId.WORKSPACE_AGENT_CHAT_USE,
        OperationId.WORKSPACE_AUTOMATION_EXECUTE,
        OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
    ),
)
def test_workspace_manager_role_allows_every_non_delete_mutation(operation) -> None:
    assert operation.value in allowed_workspace_operations(ResourceAccessRole.MANAGER)


def test_platform_operations_distinguish_member_from_admin() -> None:
    policy = AuthorizationOperationPolicy(object())

    policy.require_platform_operation(
        _actor("member"),
        OperationId.WORKSPACE_CREATE,
    )
    with pytest.raises(AuthorizationOperationError) as denied:
        policy.require_platform_operation(
            _actor("member"),
            OperationId.USER_MANAGEMENT_MANAGE,
        )

    assert (denied.value.error_code, denied.value.http_status) == (
        "PLATFORM_AUTHORIZATION_DENIED",
        403,
    )
    policy.require_platform_operation(
        _actor("admin"),
        OperationId.USER_MANAGEMENT_MANAGE,
    )
