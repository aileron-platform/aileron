from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.internal.models import (
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
)


def _plugin_request() -> dict[str, object]:
    return {
        "operationId": "d" * 32,
        "targetClient": "codex",
        "packageId": "review-helper",
        "marketplaceId": "aileron-tools",
        "remoteUrl": "git@git.example.com:team/marketplace.git",
        "registryRef": "main",
        "workspaceId": "workspace-1",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
    }


def _plugin_result() -> dict[str, object]:
    return {
        "status": "installed",
        "operationId": "d" * 32,
        "targetClient": "codex",
        "packageId": "review-helper",
        "marketplaceId": "aileron-tools",
        "workspaceId": "workspace-1",
        "stage": "completed",
        "exitCode": 0,
        "cliMessage": None,
        "stdout": "[]",
        "stderr": None,
        "truncated": False,
    }


def test_plugin_install_request_is_minimal_and_strict() -> None:
    parsed = MarketplacePluginInstallRequest.model_validate(_plugin_request())
    assert parsed.target_client == "codex"
    assert parsed.remote_url == "git@git.example.com:team/marketplace.git"

    for legacy_field in (
        "installationId",
        "operationKind",
        "expectedCommit",
        "expectedPackageTreeDigest",
    ):
        invalid = _plugin_request()
        invalid[legacy_field] = "legacy"
        with pytest.raises(ValidationError):
            MarketplacePluginInstallRequest.model_validate(invalid)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspaceId", 1),
        ("registryRef", 1),
        ("operationId", True),
        ("operationId", "11111111-1111-4111-8111-111111111111"),
    ],
)
def test_plugin_install_request_rejects_scalar_coercion(
    field: str,
    value: object,
) -> None:
    payload = _plugin_request()
    payload[field] = value
    with pytest.raises(ValidationError):
        MarketplacePluginInstallRequest.model_validate(payload)


def test_plugin_command_result_is_strict_and_terminal() -> None:
    parsed = MarketplacePluginCommandResult.model_validate(_plugin_result())
    assert parsed.status == "installed"
    assert parsed.stage == "completed"

    failed = _plugin_result()
    failed.update(
        {
            "status": "failed",
            "stage": "plugin-install",
            "exitCode": 2,
            "stderr": "permission denied",
        }
    )
    assert MarketplacePluginCommandResult.model_validate(failed).exit_code == 2

    for status, stage in (("installed", "plugin-list"), ("failed", "completed")):
        inconsistent = _plugin_result()
        inconsistent.update({"status": status, "stage": stage})
        with pytest.raises(
            ValidationError,
            match="marketplace.install.runtime_contract_invalid",
        ):
            MarketplacePluginCommandResult.model_validate(inconsistent)

    for legacy_field in (
        "installationId",
        "remoteUrl",
        "registryRef",
        "runtimeInstanceId",
    ):
        extra = _plugin_result()
        extra[legacy_field] = "legacy"
        with pytest.raises(ValidationError):
            MarketplacePluginCommandResult.model_validate(extra)
