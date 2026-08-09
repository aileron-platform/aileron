from __future__ import annotations

from pathlib import Path

import pytest

from app.config.settings import Settings
from app.modules.internal.models import MarketplacePluginInstallRequest
from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.gate import MarketplaceProviderGate
from app.modules.marketplace_operations.plugin_cli_install import (
    PluginCliInstallResult,
)
from app.modules.marketplace_operations.plugin_installation import (
    MarketplacePluginInstallService,
)
from app.modules.marketplace_operations.state import MarketplaceMutationStore

RUNTIME_ID = "11111111-1111-4111-8111-111111111111"


class _Installer:
    def __init__(self, result: PluginCliInstallResult) -> None:
        self.result = result
        self.calls: list[dict[str, str]] = []

    def install(self, **values: str) -> PluginCliInstallResult:
        self.calls.append(values)
        return self.result


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        ENV="test",
        AILERON_WORKSPACE_ID="workspace-1",
        AILERON_WORKSPACE_PATH=str(tmp_path / "workspace"),
        MARKETPLACE_OPERATION_JOURNAL_DIR=str(tmp_path / "state"),
    )


def _request(**overrides: str) -> MarketplacePluginInstallRequest:
    payload = {
        "operationId": "a" * 32,
        "provider": "codex",
        "packageId": "github",
        "marketplaceId": "private-market",
        "remoteUrl": "git@gitlab.example:team/marketplace.git",
        "publishRef": "main",
        "workspaceId": "workspace-1",
        "runtimeInstanceId": RUNTIME_ID,
    }
    payload.update(overrides)
    return MarketplacePluginInstallRequest.model_validate(payload)


def test_failed_install_returns_cli_envelope_and_clears_provider_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_calls: list[dict[str, str]] = []
    monkeypatch.setattr(
        "app.modules.marketplace_operations.plugin_installation.clear_agent_settings_cache",
        lambda **values: clear_calls.append(values),
    )
    store = MarketplaceMutationStore(tmp_path / "state")
    gate = MarketplaceProviderGate(store)
    installer = _Installer(
        PluginCliInstallResult(
            status="failed",
            stage="plugin-install",
            exit_code=9,
            cli_message="permission denied",
            stdout=None,
            stderr="permission denied",
            truncated=False,
        )
    )
    service = MarketplacePluginInstallService(
        settings=_settings(tmp_path),
        store=store,
        gate=gate,
        installer=installer,  # type: ignore[arg-type]
    )

    result = service.install(_request())

    assert result.status == "failed"
    assert result.stage == "plugin-install"
    assert result.exit_code == 9
    assert installer.calls == [
        {
            "provider": "codex",
            "package_id": "github",
            "marketplace_id": "private-market",
            "remote_url": "git@gitlab.example:team/marketplace.git",
            "publish_ref": "main",
        }
    ]
    assert gate.generation("codex") == 1
    assert clear_calls == [
        {
            "provider": "codex",
            "workspace_id": "workspace-1",
        }
    ]
    assert not (tmp_path / "state" / "operations").exists()
    assert not (tmp_path / "state" / "provider-resource-state.json").exists()


def test_success_clears_all_provider_caches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_calls: list[dict[str, str]] = []
    monkeypatch.setattr(
        "app.modules.marketplace_operations.plugin_installation.clear_agent_settings_cache",
        lambda **values: clear_calls.append(values),
    )
    service = MarketplacePluginInstallService(
        settings=_settings(tmp_path),
        installer=_Installer(
            PluginCliInstallResult(
                status="installed",
                stage="completed",
                exit_code=0,
                cli_message=None,
                stdout=None,
                stderr=None,
                truncated=False,
            )
        ),  # type: ignore[arg-type]
    )

    service.install(_request(provider="claude-code"))

    assert clear_calls == [
        {
            "provider": "claude-code",
            "workspace_id": "workspace-1",
        }
    ]


def test_service_rejects_runtime_rebind_before_cli(
    tmp_path: Path,
) -> None:
    installer = _Installer(
        PluginCliInstallResult(
            status="installed",
            stage="completed",
            exit_code=0,
            cli_message=None,
            stdout=None,
            stderr=None,
            truncated=False,
        )
    )
    service = MarketplacePluginInstallService(
        settings=_settings(tmp_path),
        installer=installer,  # type: ignore[arg-type]
    )

    with pytest.raises(MarketplaceOperationError) as exc_info:
        service.install(_request(workspaceId="other-workspace"))

    assert exc_info.value.code == "marketplace.install.runtime_rebind_failed"
    assert installer.calls == []


@pytest.mark.parametrize(
    "remote_url",
    [
        "https://user:secret@gitlab.example/team/marketplace.git",
        "ssh://user:secret@gitlab.example/team/marketplace.git",
    ],
)
def test_service_rejects_embedded_remote_credentials_before_cli(
    tmp_path: Path,
    remote_url: str,
) -> None:
    installer = _Installer(
        PluginCliInstallResult(
            status="installed",
            stage="completed",
            exit_code=0,
            cli_message=None,
            stdout=None,
            stderr=None,
            truncated=False,
        )
    )
    service = MarketplacePluginInstallService(
        settings=_settings(tmp_path),
        installer=installer,  # type: ignore[arg-type]
    )

    with pytest.raises(MarketplaceOperationError) as exc_info:
        service.install(_request(remoteUrl=remote_url))

    assert exc_info.value.code == "marketplace.install.runtime_contract_invalid"
    assert installer.calls == []
