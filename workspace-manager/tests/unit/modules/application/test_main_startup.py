from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.settings import Settings
from app.main import (
    _sync_oidc_readiness_until_ready,
    _sync_runtime_capabilities_on_startup,
    _sync_runtime_capabilities_until_ready,
    _verify_browser_turn_configuration_on_startup,
    _verify_runtime_assertion_configuration_on_startup,
    _verify_runtime_database_configuration_on_startup,
    settings,
    verify_oidc_configuration,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_startup_syncs_running_runtime_capabilities_and_closes_session() -> None:
    session = MagicMock()
    service = MagicMock()
    service.sync_running_runtime_capabilities = AsyncMock(
        return_value={"synced": 1, "failed": 0}
    )

    with (
        patch("app.main.SessionLocal", return_value=session),
        patch("app.main.RuntimeSyncService", return_value=service),
    ):
        result = await _sync_runtime_capabilities_on_startup()

    assert result == {"synced": 1, "failed": 0}
    service.sync_running_runtime_capabilities.assert_awaited_once_with()
    session.close.assert_called_once_with()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_startup_capabilities_sync_retries_until_runtime_is_ready() -> None:
    sync_once = AsyncMock(
        side_effect=[
            {"synced": 0, "failed": 1},
            {"synced": 1, "failed": 0},
        ]
    )

    with (
        patch("app.main._sync_runtime_capabilities_on_startup", sync_once),
        patch("app.main.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        await _sync_runtime_capabilities_until_ready()

    assert sync_once.await_count == 2
    sleep.assert_awaited_once_with(1)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_startup_verifies_configured_oidc_discovery(tmp_path: Path) -> None:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")
    config = Settings(
        ENV="production",
        RUNTIME_PROVISIONER="docker",
        PLATFORM_PUBLIC_ORIGIN="https://aileron.example.com",
        OIDC_ISSUER_URL="https://issuer.example.com",
        OIDC_CLIENT_ID="aileron-manager",
        OIDC_CLIENT_SECRET_FILE=str(secret_file),
        OIDC_ALLOWED_ALGORITHMS=["RS256"],
    )
    jwt_utils = MagicMock()
    jwt_utils.fetch_discovery = AsyncMock()
    jwt_utils.fetch_jwks = AsyncMock(
        return_value={"keys": [{"kid": "provider-key", "use": "sig", "alg": "RS256"}]}
    )
    await verify_oidc_configuration(config=config, jwt_utils=jwt_utils)

    assert jwt_utils.config is config
    jwt_utils.fetch_discovery.assert_awaited_once_with(force=True)
    jwt_utils.fetch_jwks.assert_awaited_once_with(force=True)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_startup_rejects_unreadable_oidc_client_secret_file(
    tmp_path: Path,
) -> None:
    config = Settings(
        ENV="production",
        RUNTIME_PROVISIONER="docker",
        PLATFORM_PUBLIC_ORIGIN="https://aileron.example.com",
        OIDC_ISSUER_URL="https://issuer.example.com",
        OIDC_CLIENT_ID="aileron-manager",
        OIDC_CLIENT_SECRET_FILE=str(tmp_path / "missing-secret"),
    )
    jwt_utils = MagicMock()

    with pytest.raises(ValueError, match="OIDC_CLIENT_SECRET_FILE"):
        await verify_oidc_configuration(config=config, jwt_utils=jwt_utils)

    jwt_utils.fetch_discovery.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_oidc_readiness_retries_without_blocking_process_liveness() -> None:
    app = MagicMock()
    verify = AsyncMock(side_effect=[RuntimeError("provider unavailable"), None])

    with (
        patch("app.main.verify_oidc_configuration", verify),
        patch("app.main.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        await _sync_oidc_readiness_until_ready(app)

    assert verify.await_count == 2
    sleep.assert_awaited_once_with(1)
    assert app.state.oidc_ready is True


@pytest.mark.unit
def test_startup_verifies_kubernetes_runtime_database_isolation() -> None:
    service = MagicMock()

    with (
        patch("app.main.settings.RUNTIME_PROVISIONER", "kubernetes"),
        patch(
            "app.main.WorkspaceRuntimeDatabaseService",
            return_value=service,
        ) as service_factory,
    ):
        _verify_runtime_database_configuration_on_startup()

    service_factory.assert_called_once()
    service.prepare.assert_called_once_with(
        workspace_id="00000000-0000-4000-8000-000000000000",
        runtime_instance_id="00000000-0000-4000-8000-000000000001",
    )


@pytest.mark.unit
def test_startup_skips_runtime_database_key_for_non_kubernetes_provisioner() -> None:
    with (
        patch("app.main.settings.RUNTIME_PROVISIONER", "docker"),
        patch("app.main.WorkspaceRuntimeDatabaseService") as service_factory,
    ):
        _verify_runtime_database_configuration_on_startup()

    service_factory.assert_not_called()


@pytest.mark.unit
def test_startup_verifies_browser_turn_credential_configuration() -> None:
    with patch(
        "app.main.BrowserTurnCredentialIssuer.from_settings"
    ) as issuer_factory:
        _verify_browser_turn_configuration_on_startup()

    issuer_factory.assert_called_once_with(settings)


@pytest.mark.unit
def test_startup_verifies_runtime_assertion_signing_authority() -> None:
    with patch("app.main.RuntimeAssertionService.from_settings") as service_factory:
        _verify_runtime_assertion_configuration_on_startup()

    service_factory.assert_called_once_with(settings)
