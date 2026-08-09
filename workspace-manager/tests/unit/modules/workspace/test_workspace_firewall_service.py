from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.modules.authorization.operation_policy import OperationId
from app.modules.workspace.firewall_contract import FirewallReplacementRequest
from app.modules.authorization.actor import AuthorizationActor
from app.db import models as db_models
from app.modules.workspace.models import WorkspaceUpdateRequest
from app.modules.workspace.firewall_command_repository import (
    WorkspaceFirewallSyncCommandRepository,
)
from app.modules.workspace.firewall import (
    WorkspaceFirewallRetryNotAllowedError,
    WorkspaceFirewallRevisionConflictError,
    WorkspaceFirewallService,
)


def _payload(revision: int, domain: str = "example.com") -> FirewallReplacementRequest:
    return FirewallReplacementRequest.model_validate(
        {
            "revision": revision,
            "workspace": {
                "egressMode": "allowlist",
                "allowedDomains": [domain],
            },
            "browser": {
                "egressMode": "blocked",
                "allowedDomains": [],
            },
        }
    )


def _workspace() -> MagicMock:
    workspace = MagicMock()
    workspace.id = "workspace-123"
    workspace.firewall_revision = 3
    workspace.firewall_observed_revision = 2
    workspace.firewall_sync_status = "applied"
    workspace.firewall_error_code = None
    workspace.firewall_target_delivery_id = "command-original"
    workspace.workspace_firewall_egress_mode = "allowlist"
    workspace.workspace_firewall_allowed_domains = ["old.example.com"]
    workspace.browser_firewall_egress_mode = "blocked"
    workspace.browser_firewall_allowed_domains = []
    return workspace


def _actor() -> AuthorizationActor:
    return AuthorizationActor(user_id="user-123", platform_role="member")


def test_general_workspace_update_rejects_firewall() -> None:
    with pytest.raises(ValidationError):
        WorkspaceUpdateRequest.model_validate({"firewall": {}})


def test_get_requires_firewall_read_operation() -> None:
    db = MagicMock()
    workspace = _workspace()
    db.get.return_value = workspace
    service = WorkspaceFirewallService(db)

    with patch.object(
        service.authorization,
        "require_workspace_operation",
    ) as require_workspace_operation:
        result = service.get(
            workspace_id=workspace.id,
            actor=_actor(),
        )

    assert result.revision == workspace.firewall_revision
    require_workspace_operation.assert_called_once_with(
        _actor(),
        workspace.id,
        OperationId.WORKSPACE_FIREWALL_READ,
    )


def test_replace_uses_revision_cas_and_enqueues_delivery() -> None:
    db = MagicMock()
    workspace = _workspace()
    db.scalar.return_value = workspace
    service = WorkspaceFirewallService(db)
    service.commands = MagicMock()

    with (
        patch("app.modules.workspace.firewall.acquire_workspace_transaction_lock"),
        patch.object(
            service.authorization,
            "require_workspace_operation",
        ) as require_workspace_operation,
    ):
        result = service.replace(
            workspace_id=workspace.id,
            actor=_actor(),
            payload=_payload(3),
        )

    assert result.changed is True
    assert result.resource.revision == 4
    assert result.resource.sync_status == "applying"
    require_workspace_operation.assert_called_once_with(
        _actor(),
        workspace.id,
        OperationId.WORKSPACE_FIREWALL_MANAGE,
    )
    service.commands.enqueue.assert_called_once()
    db.commit.assert_called_once()


def test_replace_rejects_stale_revision_without_enqueue() -> None:
    db = MagicMock()
    workspace = _workspace()
    db.scalar.return_value = workspace
    service = WorkspaceFirewallService(db)
    service.commands = MagicMock()

    with (
        patch("app.modules.workspace.firewall.acquire_workspace_transaction_lock"),
        patch.object(service.authorization, "require_workspace_operation"),
        pytest.raises(WorkspaceFirewallRevisionConflictError),
    ):
        service.replace(
            workspace_id=workspace.id,
            actor=_actor(),
            payload=_payload(2),
        )

    service.commands.enqueue.assert_not_called()
    db.rollback.assert_called_once()


def test_retry_enqueues_immutable_desired_revision_command() -> None:
    db = MagicMock()
    workspace = _workspace()
    workspace.firewall_sync_status = "error"
    workspace.firewall_error_code = "FIREWALL_APPLY_FAILED"
    db.scalar.return_value = workspace
    service = WorkspaceFirewallService(db)
    service.commands = MagicMock()
    service.commands.enqueue_retry.return_value = MagicMock()

    with (
        patch("app.modules.workspace.firewall.acquire_workspace_transaction_lock"),
        patch.object(
            service.authorization,
            "require_workspace_operation",
        ) as require_workspace_operation,
    ):
        result = service.retry(
            workspace_id=workspace.id,
            actor=_actor(),
        )

    assert result.sync_status == "applying"
    assert result.error_code is None
    require_workspace_operation.assert_called_once_with(
        _actor(),
        workspace.id,
        OperationId.WORKSPACE_FIREWALL_MANAGE,
    )
    service.commands.enqueue_retry.assert_called_once()
    db.commit.assert_called_once()


def test_retry_reenqueues_same_revision_after_attestation_expires() -> None:
    db = MagicMock()
    workspace = _workspace()
    workspace.firewall_observed_revision = workspace.firewall_revision
    workspace.firewall_sync_status = "error"
    workspace.firewall_error_code = "FIREWALL_POLICY_ENFORCEMENT_TIMEOUT"
    db.scalar.return_value = workspace
    service = WorkspaceFirewallService(db)
    service.commands = MagicMock()
    service.commands.enqueue_retry.return_value = MagicMock()

    with (
        patch("app.modules.workspace.firewall.acquire_workspace_transaction_lock"),
        patch.object(service.authorization, "require_workspace_operation"),
    ):
        result = service.retry(
            workspace_id=workspace.id,
            actor=_actor(),
        )

    assert result.revision == workspace.firewall_revision
    assert result.observed_revision == workspace.firewall_revision
    assert result.sync_status == "applying"
    service.commands.enqueue_retry.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.parametrize(
    ("sync_status", "observed_revision"),
    (("applied", 3), ("applying", 2)),
)
def test_retry_rejects_non_failed_state(
    sync_status: str,
    observed_revision: int,
) -> None:
    db = MagicMock()
    workspace = _workspace()
    workspace.firewall_sync_status = sync_status
    workspace.firewall_observed_revision = observed_revision
    db.scalar.return_value = workspace
    service = WorkspaceFirewallService(db)
    service.commands = MagicMock()

    with (
        patch("app.modules.workspace.firewall.acquire_workspace_transaction_lock"),
        patch.object(service.authorization, "require_workspace_operation"),
        pytest.raises(WorkspaceFirewallRetryNotAllowedError),
    ):
        service.retry(
            workspace_id=workspace.id,
            actor=_actor(),
        )

    service.commands.enqueue_retry.assert_not_called()
    db.rollback.assert_called_once()


def test_repository_retry_preserves_delivered_command_and_creates_lineage() -> None:
    db = MagicMock()
    delivered = MagicMock()
    delivered.id = "command-original"
    delivered.root_command_id = "command-original"
    delivered.status = "delivered"
    delivered.firewall_revision = 3
    workspace = _workspace()
    workspace.firewall_sync_status = "error"
    workspace.firewall_error_code = "FIREWALL_APPLY_FAILED"
    db.scalars.return_value.all.return_value = [delivered]
    repository = WorkspaceFirewallSyncCommandRepository(db)
    retry_at = datetime.now(timezone.utc)

    retry = repository.enqueue_retry(
        workspace=workspace,
        scheduled_at=retry_at,
    )

    assert retry is not None
    assert retry.id != delivered.id
    assert retry.retry_of_command_id == delivered.id
    assert retry.root_command_id == delivered.id
    assert retry.firewall_revision == workspace.firewall_revision
    assert retry.status == "pending"
    assert retry.attempt_count == 0
    assert retry.next_attempt_at == retry_at
    assert retry.last_error_code is None
    assert delivered.status == "delivered"
    assert workspace.firewall_target_delivery_id == retry.id
    assert workspace.firewall_sync_status == "applying"
    assert workspace.firewall_error_code is None
    db.add.assert_called_once_with(retry)
    db.flush.assert_called_once()


def test_repository_retry_command_can_be_claimed() -> None:
    db = MagicMock()
    workspace = _workspace()
    command = MagicMock()
    command.id = "command-retry"
    command.workspace_id = workspace.id
    command.firewall_revision = workspace.firewall_revision
    command.status = "pending"
    command.attempt_count = 0
    workspace.firewall_target_delivery_id = command.id
    db.scalar.return_value = command
    db.get.return_value = workspace
    repository = WorkspaceFirewallSyncCommandRepository(db)
    now = datetime.now(timezone.utc)

    claimed = repository.claim_due(
        worker_id="worker-1",
        now=now,
        lease_seconds=60,
    )

    assert claimed is command
    assert command.status == "processing"
    assert command.attempt_count == 1
    assert command.lease_owner == "worker-1"
    assert command.lease_expires_at is not None


def test_repository_retry_does_not_duplicate_active_lineage() -> None:
    db = MagicMock()
    active = MagicMock()
    active.status = "pending"
    workspace = _workspace()
    db.scalars.return_value.all.return_value = [active]
    repository = WorkspaceFirewallSyncCommandRepository(db)

    retry = repository.enqueue_retry(
        workspace=workspace,
        scheduled_at=datetime.now(timezone.utc),
    )

    assert retry is None
    db.add.assert_not_called()


def test_repository_delivered_retry_lineage_persists_and_can_be_claimed(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="firewall-owner")
    workspace_id = str(uuid4())
    command_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    with session_factory() as db:
        workspace = db_models.Workspace(
            id=workspace_id,
            owner_id=owner.id,
            name="Firewall retry",
            runtime="universal",
            provisioner="kubernetes",
            firewall_revision=2,
            firewall_observed_revision=1,
            firewall_sync_status="error",
            firewall_error_code="FIREWALL_POLICY_REJECTED",
            firewall_target_delivery_id=command_id,
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        db.add(workspace)
        db.add(
            db_models.WorkspaceFirewallSyncCommand(
                id=command_id,
                workspace_id=workspace_id,
                firewall_revision=2,
                retry_of_command_id=None,
                root_command_id=command_id,
                status="delivered",
                attempt_count=1,
                next_attempt_at=created_at,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        db.commit()

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        retry = WorkspaceFirewallSyncCommandRepository(db).enqueue_retry(
            workspace=workspace,
            scheduled_at=created_at,
        )
        assert retry is not None
        retry_id = retry.id
        db.commit()

    with session_factory() as db:
        commands = list(
            db.scalars(
                select(db_models.WorkspaceFirewallSyncCommand)
                .where(
                    db_models.WorkspaceFirewallSyncCommand.workspace_id == workspace_id
                )
                .order_by(db_models.WorkspaceFirewallSyncCommand.created_at)
            )
        )
        assert len(commands) == 2
        assert commands[0].id == command_id
        assert commands[0].status == "delivered"
        assert commands[1].id == retry_id
        assert commands[1].retry_of_command_id == command_id
        assert commands[1].root_command_id == command_id

        claimed = WorkspaceFirewallSyncCommandRepository(db).claim_due(
            worker_id="firewall-worker",
            now=created_at,
            lease_seconds=60,
        )
        assert claimed is not None
        assert claimed.id == retry_id
        assert claimed.status == "processing"


@pytest.mark.parametrize(
    ("egress_mode", "allowed_domains"),
    [
        ("allowlist", []),
        ("blocked", ["example.com"]),
        ("unrestricted", ["example.com"]),
    ],
)
def test_workspace_model_enforces_firewall_egress_domain_shape_on_sqlite(
    test_app,
    create_user,
    egress_mode: str,
    allowed_domains: list[str],
) -> None:
    _, session_factory = test_app
    owner = create_user(id=f"firewall-constraint-owner-{egress_mode}")
    with session_factory() as db:
        db.add(
            db_models.Workspace(
                id=str(uuid4()),
                owner_id=owner.id,
                name="Invalid firewall shape",
                runtime="universal",
                provisioner="docker",
                env_vars=[],
                workspace_firewall_egress_mode=egress_mode,
                workspace_firewall_allowed_domains=allowed_domains,
                browser_firewall_egress_mode="unrestricted",
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_repository_transient_failure_stays_applying_until_automatic_retry_applies(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="firewall-auto-retry-owner")
    workspace_id = str(uuid4())
    command_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    retry_at = created_at + timedelta(seconds=1)
    with session_factory() as db:
        db.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner.id,
                name="Firewall automatic retry",
                runtime="universal",
                provisioner="docker",
                firewall_revision=2,
                firewall_observed_revision=1,
                firewall_sync_status="applying",
                firewall_error_code=None,
                firewall_target_delivery_id=command_id,
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        db.add(
            db_models.WorkspaceFirewallSyncCommand(
                id=command_id,
                workspace_id=workspace_id,
                firewall_revision=2,
                retry_of_command_id=None,
                root_command_id=command_id,
                status="pending",
                attempt_count=0,
                next_attempt_at=created_at,
                created_at=created_at,
                updated_at=created_at,
            )
        )
        db.commit()

    with session_factory() as db:
        repository = WorkspaceFirewallSyncCommandRepository(db)
        claimed = repository.claim_due(
            worker_id="firewall-worker",
            now=created_at,
            lease_seconds=60,
        )
        assert claimed is not None
        assert repository.fail(
            command_id=command_id,
            worker_id="firewall-worker",
            failed_at=created_at,
            error_code="FIREWALL_DELIVERY_FAILED",
            max_attempts=2,
            base_delay_seconds=1,
            max_delay_seconds=10,
        )
        db.commit()

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        command = db.get(db_models.WorkspaceFirewallSyncCommand, command_id)
        assert command.status == "pending"
        assert command.next_attempt_at == retry_at.replace(tzinfo=None)
        assert command.last_error_code == "FIREWALL_DELIVERY_FAILED"
        assert workspace.firewall_sync_status == "applying"
        assert workspace.firewall_error_code is None

        repository = WorkspaceFirewallSyncCommandRepository(db)
        claimed = repository.claim_due(
            worker_id="firewall-worker",
            now=retry_at,
            lease_seconds=60,
        )
        assert claimed is not None
        assert claimed.id == command_id
        assert repository.complete(
            command_id=command_id,
            worker_id="firewall-worker",
            completed_at=retry_at,
            observed=True,
        )
        db.commit()

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        command = db.get(db_models.WorkspaceFirewallSyncCommand, command_id)
        assert command.status == "delivered"
        assert command.attempt_count == 2
        assert command.last_error_code is None
        assert workspace.firewall_sync_status == "applied"
        assert workspace.firewall_observed_revision == 2
        assert workspace.firewall_error_code is None


def test_stale_processing_delivery_is_superseded_before_external_mutation(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="firewall-stale-worker-owner")
    workspace_id = str(uuid4())
    previous_command_id = str(uuid4())
    current_command_id = str(uuid4())
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        workspace = db_models.Workspace(
            id=workspace_id,
            owner_id=owner.id,
            name="Firewall stale delivery",
            runtime="universal",
            provisioner="kubernetes",
            firewall_revision=2,
            firewall_observed_revision=1,
            firewall_sync_status="applying",
            firewall_error_code=None,
            firewall_target_delivery_id=current_command_id,
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        db.add(workspace)
        db.add(
            db_models.WorkspaceFirewallSyncCommand(
                id=previous_command_id,
                workspace_id=workspace_id,
                firewall_revision=2,
                retry_of_command_id=None,
                root_command_id=previous_command_id,
                status="processing",
                attempt_count=1,
                next_attempt_at=now,
                lease_owner="worker-old",
                lease_expires_at=now + timedelta(seconds=60),
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()
        db.add(
            db_models.WorkspaceFirewallSyncCommand(
                id=current_command_id,
                workspace_id=workspace_id,
                firewall_revision=2,
                retry_of_command_id=previous_command_id,
                root_command_id=previous_command_id,
                status="pending",
                attempt_count=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()

    with session_factory() as db:
        repository = WorkspaceFirewallSyncCommandRepository(db)

        locked_workspace = repository.lock_current_delivery_workspace(
            command_id=previous_command_id,
            worker_id="worker-old",
            now=now,
        )

        assert locked_workspace is None
        db.commit()

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        previous = db.get(
            db_models.WorkspaceFirewallSyncCommand,
            previous_command_id,
        )
        current = db.get(
            db_models.WorkspaceFirewallSyncCommand,
            current_command_id,
        )
        assert workspace.firewall_target_delivery_id == current_command_id
        assert previous.status == "superseded"
        assert previous.lease_owner is None
        assert previous.lease_expires_at is None
        assert current.status == "pending"


def test_lock_contention_defer_preserves_attempt_budget() -> None:
    db = MagicMock()
    workspace = _workspace()
    command = MagicMock()
    command.id = "command-current"
    command.workspace_id = workspace.id
    command.firewall_revision = workspace.firewall_revision
    command.attempt_count = 2
    workspace.firewall_target_delivery_id = command.id
    db.scalar.return_value = command
    db.get.return_value = workspace
    repository = WorkspaceFirewallSyncCommandRepository(db)
    deferred_at = datetime.now(timezone.utc)

    assert repository.defer_for_lock_contention(
        command_id=command.id,
        worker_id="worker-contended",
        deferred_at=deferred_at,
        updated_at=deferred_at - timedelta(seconds=3),
    )

    assert command.status == "pending"
    assert command.attempt_count == 1
    assert command.next_attempt_at == deferred_at
    assert command.updated_at == deferred_at - timedelta(seconds=3)
    assert command.lease_owner is None
    assert command.lease_expires_at is None
    assert command.last_error_code is None
    assert workspace.firewall_sync_status == "applying"
    assert workspace.firewall_error_code is None


def test_due_command_claim_uses_skip_locked() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    repository = WorkspaceFirewallSyncCommandRepository(db)

    assert (
        repository.claim_due(
            worker_id="worker-1",
            now=datetime.now(timezone.utc),
            lease_seconds=60,
        )
        is None
    )

    statement = db.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
