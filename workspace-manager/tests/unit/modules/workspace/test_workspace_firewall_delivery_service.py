from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.workspace.advisory_lock import (
    WorkspaceAdvisoryLockUnavailableError,
)
from app.modules.workspace.firewall_delivery import (
    WorkspaceFirewallDeliveryService,
)


@pytest.mark.unit
@pytest.mark.workspace
def test_kubernetes_delivery_forwards_immutable_command_identity():
    service = WorkspaceFirewallDeliveryService.__new__(WorkspaceFirewallDeliveryService)
    service.db = MagicMock()
    service.settings = SimpleNamespace(
        FIREWALL_SYNC_BATCH_SIZE=1,
        FIREWALL_SYNC_LEASE_SECONDS=30,
        FIREWALL_SYNC_BASE_DELAY_SECONDS=1,
    )
    service.commands = MagicMock()

    command_id = uuid4()
    workspace = SimpleNamespace(
        id=str(uuid4()),
        provisioner="kubernetes",
    )
    service.commands.claim_due.return_value = SimpleNamespace(
        id=command_id,
        workspace_id=workspace.id,
    )
    service.commands.lock_current_delivery_workspace.return_value = workspace
    service.commands.complete.return_value = True

    with patch(
        "app.modules.workspace.firewall_delivery.WorkspaceCustomResourceService"
    ) as custom_resource_service_class:
        result = service.reconcile_due(worker_id="worker-1")

    custom_resource_service_class.return_value.apply_firewall_spec.assert_called_once_with(
        workspace,
        delivery_id=str(command_id),
    )
    service.commands.complete.assert_called_once()
    assert service.commands.complete.call_args.kwargs["observed"] is False
    assert result == {"delivered": 1, "failed": 0}


@pytest.mark.unit
@pytest.mark.workspace
def test_previous_delivery_is_dropped_before_external_mutation():
    service = WorkspaceFirewallDeliveryService.__new__(WorkspaceFirewallDeliveryService)
    service.db = MagicMock()
    service.settings = SimpleNamespace(
        FIREWALL_SYNC_BATCH_SIZE=1,
        FIREWALL_SYNC_LEASE_SECONDS=30,
        FIREWALL_SYNC_BASE_DELAY_SECONDS=1,
    )
    service.commands = MagicMock()
    command_id = uuid4()
    workspace_id = str(uuid4())
    service.commands.claim_due.return_value = SimpleNamespace(
        id=command_id,
        workspace_id=workspace_id,
    )
    service.commands.lock_current_delivery_workspace.return_value = None

    with patch(
        "app.modules.workspace.firewall_delivery.WorkspaceCustomResourceService"
    ) as custom_resource_service_class:
        result = service.reconcile_due(worker_id="worker-old")

    custom_resource_service_class.assert_not_called()
    service.commands.complete.assert_not_called()
    service.commands.fail.assert_not_called()
    assert result == {"delivered": 0, "failed": 0}


@pytest.mark.unit
@pytest.mark.workspace
def test_workspace_lock_contention_defers_without_consuming_delivery_attempt():
    service = WorkspaceFirewallDeliveryService.__new__(WorkspaceFirewallDeliveryService)
    service.db = MagicMock()
    service.settings = SimpleNamespace(
        FIREWALL_SYNC_BATCH_SIZE=1,
        FIREWALL_SYNC_LEASE_SECONDS=30,
        FIREWALL_SYNC_BASE_DELAY_SECONDS=3,
    )
    service.commands = MagicMock()
    command_id = uuid4()
    workspace_id = str(uuid4())
    service.commands.claim_due.return_value = SimpleNamespace(
        id=command_id,
        workspace_id=workspace_id,
    )

    with patch(
        "app.modules.workspace.firewall_delivery.workspace_session_advisory_lock",
        side_effect=WorkspaceAdvisoryLockUnavailableError(
            "Workspace advisory lock is already owned"
        ),
    ):
        result = service.reconcile_due(worker_id="worker-contended")

    service.commands.defer_for_lock_contention.assert_called_once()
    assert (
        service.commands.defer_for_lock_contention.call_args.kwargs["command_id"]
        == command_id
    )
    assert (
        service.commands.defer_for_lock_contention.call_args.kwargs["worker_id"]
        == "worker-contended"
    )
    service.commands.fail.assert_not_called()
    assert result == {"delivered": 0, "failed": 0}
