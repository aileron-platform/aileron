"""One-shot Runtime orchestration for target_client CLI plugin installation."""

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
from .gate import MarketplaceTargetClientGate
from .plugin_cli_install import TargetClientPluginCliInstaller
from .state import MarketplaceMutationStore

_URI_CREDENTIALS = re.compile(
    r"^[A-Za-z][A-Za-z0-9+.-]*://[^/\s@]+@",
)


class MarketplacePluginInstallService:
    """Serialize one target_client CLI installation without retaining lifecycle state."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        store: MarketplaceMutationStore | None = None,
        gate: MarketplaceTargetClientGate | None = None,
        installer: TargetClientPluginCliInstaller | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._store = store or MarketplaceMutationStore(
            Path(self._settings.MARKETPLACE_OPERATION_JOURNAL_DIR)
        )
        self._gate = gate or MarketplaceTargetClientGate(self._store)
        self._installer = installer or TargetClientPluginCliInstaller()

    def install(
        self,
        request: MarketplacePluginInstallRequest,
    ) -> MarketplacePluginCommandResult:
        """Run the CLI sequence and return its bounded terminal result."""

        self._validate_request(request)
        with self._store.target_client_lock(
            target_client=request.target_client,
        ):
            outcome = self._installer.install(
                target_client=request.target_client,
                package_id=request.package_id,
                marketplace_id=request.marketplace_id,
                remote_url=request.remote_url,
                registry_ref=request.registry_ref,
            )
            self._gate.advance_generation(request.target_client)
            clear_agent_settings_cache(
                provider=request.target_client,
                workspace_id=request.workspace_id,
            )
        return MarketplacePluginCommandResult(
            status=outcome.status,
            operationId=request.operation_id,
            targetClient=request.target_client,
            packageId=request.package_id,
            marketplaceId=request.marketplace_id,
            workspaceId=request.workspace_id,
            stage=outcome.stage,
            exitCode=outcome.exit_code,
            cliMessage=outcome.cli_message,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            truncated=outcome.truncated,
            commands=[
                {
                    "sequence": command.sequence,
                    "stage": command.stage,
                    "argvDisplay": command.argv_display,
                    "exitCode": command.exit_code,
                    "startedAt": command.started_at,
                    "endedAt": command.ended_at,
                    "stdout": command.stdout,
                    "stderr": command.stderr,
                    "stdoutOriginalByteCount": command.stdout_original_byte_count,
                    "stderrOriginalByteCount": command.stderr_original_byte_count,
                    "truncated": command.truncated,
                }
                for command in outcome.commands
            ],
            warnings=list(outcome.warnings),
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
        for value in (request.remote_url, request.registry_ref):
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
