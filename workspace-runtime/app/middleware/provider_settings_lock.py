"""Serialize public provider settings writes with Marketplace operations."""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.gate import get_marketplace_provider_gate

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _provider_from_path(path: str) -> str | None:
    segments = [segment for segment in path.split("/") if segment]
    try:
        workspace_index = segments.index("workspaces")
        provider_segment = segments[workspace_index + 2]
    except (ValueError, IndexError):
        return None
    if provider_segment == "codex":
        return "codex"
    if provider_segment == "claude-code":
        return "claude-code"
    return None


class ProviderSettingsMutationMiddleware(BaseHTTPMiddleware):
    """Hold the provider operation lock for every public settings mutation."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        provider = (
            _provider_from_path(request.url.path)
            if request.method in {*_MUTATING_METHODS, "GET"}
            else None
        )
        if provider is None:
            return await call_next(request)

        gate = get_marketplace_provider_gate()
        try:
            if request.method == "GET" or request.url.path.endswith(
                "/codex/rules/validate"
            ):
                return await call_next(request)
            with gate.settings_mutation_scope(provider):
                previous_generation = gate.generation(provider)
                response = await call_next(request)
                if response.status_code < 400:
                    gate.complete_settings_mutation(
                        provider,
                        previous_generation=previous_generation,
                    )
                return response
        except MarketplaceOperationError as exc:
            return JSONResponse(
                status_code=exc.http_status,
                content={"errorCode": exc.code},
            )


__all__ = ["ProviderSettingsMutationMiddleware"]
