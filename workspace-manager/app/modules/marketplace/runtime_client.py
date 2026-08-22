"""HTTP client for Marketplace Runtime commands."""

from __future__ import annotations

from typing import Any

import httpx
from aileron_marketplace_core import (
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionApplyResultContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopyProjectionPreflightResultContract,
)
from pydantic import ValidationError

from app.modules.workspace.runtime.command_auth import runtime_command_headers


class MarketplaceRuntimeClientError(RuntimeError):
    """Raised when a runtime operation cannot return a typed response."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class MarketplaceRuntimeClient:
    """Call one-shot plugin install and user-copy Runtime contracts."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 130,
        client_factory: type[httpx.Client] = httpx.Client,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.client_factory = client_factory

    def descriptor(
        self,
        *,
        runtime_url: str,
        workspace_id: str,
        runtime_instance_id: str,
    ) -> dict[str, Any]:
        """Read the signed Runtime descriptor used to bind operation state."""

        return self._request(
            "GET",
            f"{runtime_url.rstrip('/')}/api/v1/internal/health",
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            action="runtime.inspect",
        )

    def install_plugin(
        self,
        *,
        runtime_url: str,
        workspace_id: str,
        runtime_instance_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one target client CLI installation and return its terminal result."""

        return self._request(
            "POST",
            f"{runtime_url.rstrip('/')}/api/v1/internal/marketplace/plugins/install",
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            action="marketplace.execute",
            payload=payload,
        )

    def preflight_user_copy(
        self,
        *,
        runtime_url: str,
        workspace_id: str,
        runtime_instance_id: str,
        request: UserCopyProjectionPreflightRequestContract,
    ) -> UserCopyProjectionPreflightResultContract:
        """Read a one-shot user-copy plan without creating Runtime state."""

        payload = self._request(
            "POST",
            f"{runtime_url.rstrip('/')}/api/v1/internal/marketplace/user-copies/preflight",
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            action="marketplace.inspect",
            payload=request.to_wire(exclude_unset=True),
            failure_code="marketplace.user_copy.runtime_delegation_unavailable",
            contract_failure_code="marketplace.user_copy.runtime_contract_invalid",
        )
        try:
            return UserCopyProjectionPreflightResultContract.from_wire(payload)
        except ValidationError as exc:
            raise MarketplaceRuntimeClientError(
                "marketplace.user_copy.runtime_contract_invalid"
            ) from exc

    def apply_user_copy(
        self,
        *,
        runtime_url: str,
        workspace_id: str,
        runtime_instance_id: str,
        metadata: UserCopyProjectionApplyMetadataContract,
        bundle: bytes,
    ) -> UserCopyProjectionApplyResultContract:
        """Upload and apply one operation-bound canonical sparse package."""

        headers = runtime_command_headers(
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            action="marketplace.execute",
        )
        headers.pop("Content-Type", None)
        files: dict[str, tuple[str | None, bytes | str, str | None]] = {
            "metadata": (
                None,
                metadata.to_wire_json(),
                "application/json",
            ),
            "bundle": ("package.zip", bundle, "application/zip"),
        }
        try:
            with self.client_factory(timeout=self.timeout_seconds) as client:
                response = client.post(
                    (
                        f"{runtime_url.rstrip('/')}/api/v1/internal/"
                        "marketplace/user-copies/apply"
                    ),
                    headers=headers,
                    files=files,
                )
                if response.is_error:
                    raise MarketplaceRuntimeClientError(
                        self._response_error_code(
                            response,
                            fallback_code=(
                                "marketplace.user_copy.runtime_contract_invalid"
                                if response.status_code == 422
                                else (
                                    "marketplace.user_copy."
                                    "runtime_delegation_unavailable"
                                )
                            ),
                        )
                    )
                result = response.json()
        except MarketplaceRuntimeClientError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketplaceRuntimeClientError(
                "marketplace.user_copy.runtime_delegation_unavailable"
            ) from exc
        if not isinstance(result, dict):
            raise MarketplaceRuntimeClientError(
                "marketplace.user_copy.runtime_contract_invalid"
            )
        try:
            return UserCopyProjectionApplyResultContract.from_wire(result)
        except ValidationError as exc:
            raise MarketplaceRuntimeClientError(
                "marketplace.user_copy.runtime_contract_invalid"
            ) from exc

    def _request(
        self,
        method: str,
        url: str,
        *,
        workspace_id: str,
        runtime_instance_id: str,
        action: str,
        payload: dict[str, Any] | None = None,
        failure_code: str = "marketplace.install.runtime_delegation_unavailable",
        contract_failure_code: str = "marketplace.install.runtime_contract_invalid",
    ) -> dict[str, Any]:
        headers = runtime_command_headers(
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            action=action,
        )
        try:
            with self.client_factory(timeout=self.timeout_seconds) as client:
                response = client.request(
                    method,
                    url,
                    json=payload,
                    headers=headers,
                )
                if response.is_error:
                    raise MarketplaceRuntimeClientError(
                        self._response_error_code(
                            response,
                            fallback_code=(
                                contract_failure_code
                                if response.status_code == 422
                                else failure_code
                            ),
                        )
                    )
                if response.status_code == 204:
                    return {}
                result = response.json()
        except MarketplaceRuntimeClientError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketplaceRuntimeClientError(failure_code) from exc
        if not isinstance(result, dict):
            raise MarketplaceRuntimeClientError(contract_failure_code)
        return result

    @staticmethod
    def _response_error_code(
        response: httpx.Response,
        *,
        fallback_code: str = "marketplace.install.runtime_delegation_unavailable",
    ) -> str:
        try:
            payload = response.json()
        except ValueError:
            return fallback_code
        if not isinstance(payload, dict):
            return fallback_code
        detail = payload.get("detail")
        if isinstance(detail, dict):
            code = detail.get("code")
            if isinstance(code, str) and code.startswith("marketplace."):
                return code
        return fallback_code
