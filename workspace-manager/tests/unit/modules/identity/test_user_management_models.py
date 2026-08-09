"""User management data contract tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.db import models as db_models
from app.db.database import Base
from app.modules.identity.admin_models import (
    AdminUser,
    admin_user_from_model,
    derive_account_state,
)
from app.modules.knowledge_base.models import KnowledgeBaseShareCreateRequest
from app.modules.identity.group_models import UserGroup
from app.modules.workspace.models import WorkspaceCreateRequest, WorkspaceUpdateRequest


def test_user_authorization_columns_are_available_without_freshness_state() -> None:
    columns = Base.metadata.tables["users"].columns

    for column_name in [
        "identity_enabled",
        "sync_status",
        "platform_role",
        "role_status",
        "role_issues",
        "last_synced_at",
    ]:
        assert column_name in columns

    assert {
        "roles",
        "last_reconciled_at",
        "last_identity_checked_at",
        "freshness_state",
        "freshness_state_changed_at",
    }.isdisjoint(columns.keys())
    assert columns["role_issues"].nullable is False
    assert str(columns["role_issues"].server_default.arg) == "'[]'"


def test_user_management_tables_use_workspace_scoped_runtime_contract() -> None:
    for table_name in [
        "user_groups",
        "user_group_members",
        "audit_events",
        "workspace_knowledge_base_attachments",
        "workspace_runtime_jobs",
    ]:
        assert table_name in Base.metadata.tables

    for removed_table_name in [
        "permission_change_outbox",
        "runtime_knowledge_base_mounts",
        "kb_access_versions",
    ]:
        assert removed_table_name not in Base.metadata.tables


def test_workspace_mount_and_access_revision_columns_are_available() -> None:
    columns = Base.metadata.tables["workspaces"].columns

    for column_name in [
        "knowledge_base_mount_desired_revision",
        "knowledge_base_mount_observed_revision",
        "knowledge_base_mount_sync_status",
        "knowledge_base_mount_error_code",
        "runtime_access_revision",
        "runtime_access_observed_revision",
        "runtime_instance_id",
        "browser_instance_id",
        "canvas_instance_id",
        "terminal_internal_url",
        "provisioner",
        "target_namespace",
    ]:
        assert column_name in columns

    assert "runtime_mounted_kb_signature" not in columns
    assert columns["knowledge_base_mount_desired_revision"].nullable is False
    assert columns["knowledge_base_mount_observed_revision"].nullable is False
    assert columns["runtime_access_revision"].nullable is False
    assert columns["runtime_access_observed_revision"].nullable is False
    assert columns["provisioner"].nullable is False

    runtime_status_constraint = next(
        constraint
        for constraint in Base.metadata.tables["workspaces"].constraints
        if constraint.name == "workspaces_runtime_status_check"
    )
    assert "stopping" in str(runtime_status_constraint.sqltext)
    assert "creating" not in str(runtime_status_constraint.sqltext)
    runtime_control_generation_constraint = next(
        constraint
        for constraint in Base.metadata.tables["workspaces"].constraints
        if constraint.name == "workspaces_runtime_control_generation_check"
    )
    assert "runtime_instance_id = runtime_control_instance_id" in str(
        runtime_control_generation_constraint.sqltext
    )


def test_workspace_public_models_forbid_deployment_fields() -> None:
    for request_model in (WorkspaceCreateRequest, WorkspaceUpdateRequest):
        assert {"provisioner", "target_namespace"}.isdisjoint(
            request_model.model_fields
        )
        assert request_model.model_config["extra"] == "forbid"

    assert "runtime_status" not in WorkspaceUpdateRequest.model_fields

    invalid_payloads = (
        (
            WorkspaceCreateRequest,
            {
                "name": "Workspace",
                "runtime": "universal",
                "provisioner": "kubernetes",
            },
        ),
        (
            WorkspaceCreateRequest,
            {
                "name": "Workspace",
                "runtime": "universal",
                "targetNamespace": "workspace-system",
            },
        ),
        (WorkspaceUpdateRequest, {"provisioner": "kubernetes"}),
        (WorkspaceUpdateRequest, {"targetNamespace": "workspace-system"}),
    )
    for request_model, payload in invalid_payloads:
        with pytest.raises(ValidationError) as exc_info:
            request_model.model_validate(payload)

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_workspace_attachment_is_last_known_good_projection_only() -> None:
    table = Base.metadata.tables["workspace_knowledge_base_attachments"]
    columns = table.columns

    assert {
        "state",
        "detach_target_revision",
        "detaching_at",
        "mode",
    }.isdisjoint(columns.keys())
    assert columns["attached_by_id"].nullable is True

    foreign_keys = {
        foreign_key.parent.name: foreign_key for foreign_key in table.foreign_keys
    }
    assert foreign_keys["kb_id"].ondelete == "RESTRICT"
    assert foreign_keys["attached_by_id"].ondelete == "SET NULL"


def test_workspace_runtime_job_uses_durable_revision_contract() -> None:
    table = Base.metadata.tables["workspace_runtime_jobs"]
    columns = table.columns

    assert {
        "target_revision",
        "target_runtime_instance_id",
        "correlation_id",
        "root_correlation_id",
        "job_metadata",
        "lifecycle_job_id",
        "retry_of_job_id",
        "claim_token",
        "claim_expires_at",
        "last_heartbeat_at",
        "dispatch_attempts",
        "error_code",
    } <= set(columns.keys())
    assert "error_message" not in columns
    assert columns["correlation_id"].nullable is False
    assert columns["root_correlation_id"].nullable is False
    assert columns["job_metadata"].nullable is False
    assert columns["dispatch_attempts"].nullable is False

    constraint_sql = " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    )
    for operation in [
        "knowledge_base_mount_reconcile",
        "workspace_access_recycle",
        "workspace_start",
        "workspace_stop",
        "workspace_delete",
        "runtime_restart",
        "browser_restart",
        "canvas_restart",
        "browser_credential_rotate",
    ]:
        assert operation in constraint_sql

    indexes = {index.name: index for index in table.indexes}
    for name in {
        "uq_workspace_runtime_jobs_queued_workspace_operation",
        "uq_workspace_runtime_jobs_running_workspace_operation",
        "uq_workspace_runtime_jobs_queued_component_operation",
        "uq_workspace_runtime_jobs_running_component_operation",
    }:
        assert indexes[name].unique is True


def test_audit_event_uses_persistent_lineage_contract() -> None:
    table = Base.metadata.tables["audit_events"]
    columns = table.columns

    assert {
        "id",
        "event_type",
        "actor_type",
        "actor_id",
        "actor_user_id",
        "target_type",
        "target_id",
        "action",
        "result",
        "error_code",
        "correlation_id",
        "root_correlation_id",
        "event_metadata",
        "created_at",
    } == set(columns.keys())
    assert {"resource_type", "resource_id"}.isdisjoint(columns.keys())
    assert columns["actor_user_id"].nullable is True
    assert columns["correlation_id"].nullable is False
    assert columns["root_correlation_id"].nullable is False
    assert columns["event_metadata"].nullable is False

    actor_foreign_key = next(iter(columns["actor_user_id"].foreign_keys))
    assert actor_foreign_key.target_fullname == "users.id"
    assert actor_foreign_key.ondelete == "SET NULL"

    constraint_sql = " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    )
    for value in [
        "user",
        "service",
        "success",
        "failure",
        "compensation_required",
    ]:
        assert value in constraint_sql

    assert {
        "ix_audit_events_correlation_created",
        "ix_audit_events_root_correlation_created",
        "ix_audit_events_target_created",
    } == {index.name for index in table.indexes}


def test_knowledge_base_share_uses_target_contract() -> None:
    table = Base.metadata.tables["knowledge_base_shares"]
    columns = table.columns

    assert "target_type" in columns
    assert "target_id" in columns
    assert "user_id" not in columns

    unique_constraints = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("kb_id", "target_type", "target_id") in unique_constraints


def test_admin_user_camel_model_outputs_frontend_contract() -> None:
    user = AdminUser(
        id="user-1",
        issuer="https://issuer.example",
        subject="oidc-subject-1",
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Lee",
        enabled=True,
        local_active=True,
        identity_enabled=True,
        account_state="active",
        role="admin",
        role_status="valid",
        role_issues=[],
        sync_status="synced",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )

    payload = user.model_dump(by_alias=True)

    assert payload["issuer"] == "https://issuer.example"
    assert payload["subject"] == "oidc-subject-1"
    assert payload["localActive"] is True
    assert payload["identityEnabled"] is True
    assert payload["roleStatus"] == "valid"


def test_user_group_camel_model_outputs_frontend_contract() -> None:
    group = UserGroup(
        id="group-1",
        name="Support",
        description=None,
        member_count=3,
        knowledge_base_share_count=2,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )

    payload = group.model_dump(by_alias=True)
    assert payload["memberCount"] == 3
    assert payload["knowledgeBaseShareCount"] == 2


def test_target_share_request_accepts_user_group() -> None:
    request = KnowledgeBaseShareCreateRequest(
        target_type="user_group",
        target_id="group-1",
        role="member",
    )

    assert request.target_type == "user_group"
    assert request.model_dump(by_alias=True)["targetId"] == "group-1"


def test_derive_account_state_prioritizes_failed_sync() -> None:
    user = db_models.User(
        id="user-1",
        username="alice",
        is_active=True,
        identity_enabled=True,
        sync_status="identity_sync_failed",
    )

    assert derive_account_state(user) == "sync_failed"


def test_admin_user_enabled_requires_authorizable_sync_status() -> None:
    observed_at = datetime(2026, 1, 1)
    user = db_models.User(
        id="user-1",
        username="alice",
        is_active=True,
        identity_enabled=True,
        sync_status="identity_sync_failed",
        platform_role="admin",
        role_status="valid",
        role_issues=[],
        created_at=observed_at,
        updated_at=observed_at,
    )

    assert admin_user_from_model(user).enabled is False
