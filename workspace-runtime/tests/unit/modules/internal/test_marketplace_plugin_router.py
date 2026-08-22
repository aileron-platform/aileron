from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.modules.internal.dependencies import (
    get_internal_service,
    verify_manager_assertion,
)
from app.modules.internal.models import (
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
)
from app.modules.internal.router import install_marketplace_plugin
from app.modules.internal.router import router as internal_router
from app.modules.marketplace_operations.errors import MarketplaceOperationError

RUNTIME_ID = "11111111-1111-4111-8111-111111111111"


def _request() -> MarketplacePluginInstallRequest:
    return MarketplacePluginInstallRequest(
        operationId="a" * 32,
        targetClient="codex",
        packageId="github",
        marketplaceId="private-market",
        remoteUrl="git@gitlab.example:team/marketplace.git",
        registryRef="main",
        workspaceId="workspace-1",
        runtimeInstanceId=RUNTIME_ID,
    )


def _failed_result() -> MarketplacePluginCommandResult:
    return MarketplacePluginCommandResult(
        status="failed",
        operationId="a" * 32,
        targetClient="codex",
        packageId="github",
        marketplaceId="private-market",
        workspaceId="workspace-1",
        stage="plugin-install",
        exitCode=128,
        cliMessage="permission denied",
        stdout=None,
        stderr="permission denied",
        truncated=False,
    )


@pytest.mark.asyncio
async def test_cli_failure_is_returned_as_typed_200_response_body() -> None:
    service = SimpleNamespace(
        install_marketplace_plugin=AsyncMock(return_value=_failed_result())
    )

    result = await install_marketplace_plugin(_request(), service)

    assert result.status == "failed"
    assert result.stage == "plugin-install"
    assert result.exit_code == 128
    service.install_marketplace_plugin.assert_awaited_once_with(_request())


def test_cli_failure_is_http_200_on_internal_endpoint() -> None:
    service = SimpleNamespace(
        install_marketplace_plugin=AsyncMock(return_value=_failed_result())
    )
    app = FastAPI()
    app.include_router(internal_router, prefix="/api/v1")
    app.dependency_overrides[verify_manager_assertion] = lambda: None
    app.dependency_overrides[get_internal_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/internal/marketplace/plugins/install",
            json=_request().model_dump(by_alias=True),
        )

    assert response.status_code == 200
    assert response.json() == _failed_result().model_dump(by_alias=True)


@pytest.mark.asyncio
async def test_identity_contract_error_remains_http_error() -> None:
    service = SimpleNamespace(
        install_marketplace_plugin=AsyncMock(
            side_effect=MarketplaceOperationError(
                "marketplace.install.runtime_rebind_failed",
                http_status=409,
            )
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await install_marketplace_plugin(_request(), service)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {
        "code": "marketplace.install.runtime_rebind_failed"
    }
