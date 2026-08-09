"""Focused tests for one-shot Marketplace CLI installation coordination."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.modules.marketplace.models import MarketplacePluginInstallRequest
from app.modules.marketplace.cli_install import (
    MarketplaceCliInstallService,
)
from app.modules.marketplace.runtime_client import MarketplaceRuntimeClientError

NOW = datetime(2026, 7, 26, tzinfo=timezone.utc)
OPERATION_ID = "a" * 32


def _request() -> MarketplacePluginInstallRequest:
    return MarketplacePluginInstallRequest(
        provider="codex",
        package_id="github",
        revision="a" * 64,
        workspace_id="workspace-1",
    )


def _result(*, status: str = "installed") -> dict[str, object]:
    return {
        "status": status,
        "provider": "codex",
        "packageId": "github",
        "marketplaceId": "private-marketplace",
        "workspaceId": "workspace-1",
        "operationId": OPERATION_ID,
        "stage": "completed" if status == "installed" else "plugin-install",
        "exitCode": 0 if status == "installed" else 1,
        "cliMessage": None if status == "installed" else "CLI rejected install",
        "stdout": "installed" if status == "installed" else None,
        "stderr": None if status == "installed" else "failed",
        "truncated": False,
    }


def _service(
    *,
    runtime_result: dict[str, object] | None = None,
    use_default_operation_id: bool = False,
) -> tuple[MarketplaceCliInstallService, Mock, Mock, Mock, Mock, Mock]:
    db = Mock()
    registry = Mock()
    runtime_client = Mock()
    activities = Mock()
    workspace_access = Mock()
    workspace_access.actor_can_mutate.return_value = True
    registry.resolve_published_package_for_install.return_value = SimpleNamespace(
        marketplace_id="private-marketplace",
        remote_url="git@gitlab.example:team/marketplace.git",
        publish_ref="main",
    )
    registry.resolve_install_runtime.return_value = {
        "runtimeUrl": "http://runtime/",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "errorCode": None,
    }
    runtime_client.install_plugin.return_value = runtime_result or _result()
    service = MarketplaceCliInstallService(
        db,
        registry,
        runtime_client=runtime_client,
        activity_repository=activities,
        workspace_access=workspace_access,
        operation_id_factory=(
            None if use_default_operation_id else lambda: OPERATION_ID
        ),
        now=lambda: NOW,
    )
    return service, db, registry, runtime_client, activities, workspace_access


def test_install_resolves_published_package_then_calls_runtime_with_minimal_contract() -> (
    None
):
    service, db, registry, runtime_client, activities, workspace_access = _service()

    result = service.install("user-1", _request())

    workspace_access.actor_can_mutate.assert_called_once_with(
        workspace_id="workspace-1",
        user_id="user-1",
    )
    registry.resolve_published_package_for_install.assert_called_once_with(
        "user-1",
        "codex",
        "github",
        "a" * 64,
    )
    runtime_client.install_plugin.assert_called_once_with(
        runtime_url="http://runtime",
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        payload={
            "operationId": OPERATION_ID,
            "provider": "codex",
            "packageId": "github",
            "marketplaceId": "private-marketplace",
            "remoteUrl": "git@gitlab.example:team/marketplace.git",
            "publishRef": "main",
            "workspaceId": "workspace-1",
            "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        },
    )
    assert result.status == "installed"
    assert result.stage == "completed"
    activities.append.assert_called_once_with(
        actor_user_id="user-1",
        action="install",
        status="succeeded",
        provider="codex",
        package_id="github",
        operation_id=OPERATION_ID,
        workspace_id="workspace-1",
        marketplace_id="private-marketplace",
        error_code=None,
        now=NOW,
    )
    db.commit.assert_called_once_with()


def test_default_operation_id_is_runtime_compatible_lowercase_hex() -> None:
    service, _db, _registry, runtime_client, _activities, _workspace_access = _service(
        use_default_operation_id=True
    )
    runtime_client.install_plugin.side_effect = lambda **kwargs: {
        **_result(),
        "operationId": kwargs["payload"]["operationId"],
    }

    result = service.install("user-1", _request())

    operation_id = runtime_client.install_plugin.call_args.kwargs["payload"][
        "operationId"
    ]
    assert re.fullmatch(r"[0-9a-f]{32}", operation_id)
    assert result.operation_id == operation_id


def test_cli_failure_is_returned_and_audited_without_http_exception() -> None:
    service, _db, _registry, _runtime_client, activities, _workspace_access = _service(
        runtime_result=_result(status="failed")
    )

    result = service.install("user-1", _request())

    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.cli_message == "CLI rejected install"
    assert activities.append.call_args.kwargs["status"] == "failed"
    assert (
        activities.append.call_args.kwargs["error_code"]
        == "marketplace.install.cli_failed"
    )


def test_resolution_failure_never_calls_runtime_and_appends_terminal_audit() -> None:
    service, _db, registry, runtime_client, activities, _workspace_access = _service()
    registry.resolve_published_package_for_install.side_effect = RuntimeError(
        "marketplace.install.package_not_published"
    )

    with pytest.raises(RuntimeError, match="marketplace.install.package_not_published"):
        service.install("user-1", _request())

    runtime_client.install_plugin.assert_not_called()
    assert activities.append.call_args.kwargs["status"] == "failed"
    assert (
        activities.append.call_args.kwargs["error_code"]
        == "marketplace.install.package_not_published"
    )


def test_runtime_identity_mismatch_is_contract_error() -> None:
    mismatched = _result()
    mismatched["workspaceId"] = "workspace-2"
    service, _db, _registry, _runtime_client, activities, _workspace_access = _service(
        runtime_result=mismatched
    )

    with pytest.raises(MarketplaceRuntimeClientError) as exc_info:
        service.install("user-1", _request())

    assert exc_info.value.code == "marketplace.install.runtime_contract_invalid"
    assert activities.append.call_args.kwargs["status"] == "failed"


def test_repeat_request_calls_resolution_and_runtime_again() -> None:
    service, _db, registry, runtime_client, _activities, _workspace_access = _service()

    service.install("user-1", _request())
    service.install("user-1", _request())

    assert registry.resolve_published_package_for_install.call_count == 2
    assert runtime_client.install_plugin.call_count == 2
