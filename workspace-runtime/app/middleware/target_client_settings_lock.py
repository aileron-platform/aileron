"""Serialize public target_client settings writes with Marketplace operations."""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.gate import get_marketplace_target_client_gate

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _target_client_from_path(path: str) -> str | None:
    segments = [segment for segment in path.split("/") if segment]
    try:
        workspace_index = segments.index("workspaces")
        target_client_segment = segments[workspace_index + 2]
    except (ValueError, IndexError):
        return None
    if target_client_segment == "codex":
        return "codex"
    if target_client_segment == "claude-code":
        return "claude-code"
    return None


class TargetClientSettingsMutationMiddleware(BaseHTTPMiddleware):
    """Hold the target_client operation lock for every public settings mutation."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        target_client = (
            _target_client_from_path(request.url.path)
            if request.method in {*_MUTATING_METHODS, "GET"}
            else None
        )
        if target_client is None:
            return await call_next(request)

        gate = get_marketplace_target_client_gate()
        try:
            if request.method == "GET" or request.url.path.endswith(
                "/codex/rules/validate"
            ):
                return await call_next(request)
            with gate.settings_mutation_scope(target_client):
                previous_generation = gate.generation(target_client)
                response = await call_next(request)
                if response.status_code < 400:
                    gate.complete_settings_mutation(
                        target_client,
                        previous_generation=previous_generation,
                    )
                return response
        except MarketplaceOperationError as exc:
            return JSONResponse(
                status_code=exc.http_status,
                content={"errorCode": exc.code},
            )


__all__ = ["TargetClientSettingsMutationMiddleware"]
