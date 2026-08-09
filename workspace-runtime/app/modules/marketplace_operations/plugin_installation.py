"""One-shot Runtime orchestration for provider CLI plugin installation."""

from __future__ import annotations

import re
from pathlib import Path

from app.config.settings import Settings, get_settings
from app.modules.cli_settings.cache_api import clear_agent_settings_cache
from app.modules.internal.models import (
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
)

from .errors import MarketplaceOperationError
from .gate import MarketplaceProviderGate
from .plugin_cli_install import ProviderPluginCliInstaller
from .state import MarketplaceMutationStore

_URI_CREDENTIALS = re.compile(
    r"^[A-Za-z][A-Za-z0-9+.-]*://[^/\s@]+@",
)


class MarketplacePluginInstallService:
    """Serialize one provider CLI installation without retaining lifecycle state."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        store: MarketplaceMutationStore | None = None,
        gate: MarketplaceProviderGate | None = None,
        installer: ProviderPluginCliInstaller | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._store = store or MarketplaceMutationStore(
            Path(self._settings.MARKETPLACE_OPERATION_JOURNAL_DIR)
        )
        self._gate = gate or MarketplaceProviderGate(self._store)
        self._installer = installer or ProviderPluginCliInstaller()

    def install(
        self,
        request: MarketplacePluginInstallRequest,
    ) -> MarketplacePluginCommandResult:
        """Run the CLI sequence and return its bounded terminal result."""

        self._validate_request(request)
        with self._store.provider_lock(
            provider=request.provider,
        ):
            outcome = self._installer.install(
                provider=request.provider,
                package_id=request.package_id,
                marketplace_id=request.marketplace_id,
                remote_url=request.remote_url,
                publish_ref=request.publish_ref,
            )
            self._gate.advance_generation(request.provider)
            clear_agent_settings_cache(
                provider=request.provider,
                workspace_id=request.workspace_id,
            )
        return MarketplacePluginCommandResult(
            status=outcome.status,
            operationId=request.operation_id,
            provider=request.provider,
            packageId=request.package_id,
            marketplaceId=request.marketplace_id,
            workspaceId=request.workspace_id,
            stage=outcome.stage,
            exitCode=outcome.exit_code,
            cliMessage=outcome.cli_message,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            truncated=outcome.truncated,
        )

    def _validate_request(
        self,
        request: MarketplacePluginInstallRequest,
    ) -> None:
        if (
            request.workspace_id != self._settings.AILERON_WORKSPACE_ID
            or request.runtime_instance_id != self._settings.AILERON_RUNTIME_INSTANCE_ID
        ):
            raise MarketplaceOperationError(
                "marketplace.install.runtime_rebind_failed",
                http_status=409,
            )
        for value in (request.remote_url, request.publish_ref):
            if value != value.strip() or any(
                ord(character) < 32 for character in value
            ):
                raise MarketplaceOperationError(
                    "marketplace.install.runtime_contract_invalid",
                    http_status=422,
                )
        if _URI_CREDENTIALS.match(request.remote_url):
            raise MarketplaceOperationError(
                "marketplace.install.runtime_contract_invalid",
                http_status=422,
            )


__all__ = ["MarketplacePluginInstallService"]
