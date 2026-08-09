"""Internal API dependency injection"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.modules.auth.manager_assertion import (
    ManagerAssertionConflict,
    ManagerAssertionInvalid,
    get_manager_assertion_verifier,
)

from .commands import InternalService

logger = logging.getLogger(__name__)


async def verify_manager_assertion(
    request: Request,
    authorization: Annotated[
        str | None, Header(description="Internal API authentication Token")
    ] = None,
) -> None:
    """Verify a short-lived Manager command assertion."""
    if request.url.path.rstrip("/") == "/api/v1/internal/runtime/drain":
        return
    assertion = None
    if authorization and authorization.startswith("Bearer "):
        assertion = authorization[7:].strip()
    if not assertion:
        logger.warning("Manager command assertion is missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "RUNTIME_ASSERTION_MISSING"},
        )
    action = _manager_command_action(
        request.url.path,
        method=request.method,
    )
    if action is None:
        logger.warning("Manager command path is not authorized: %s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "RUNTIME_ASSERTION_INVALID"},
        )
    try:
        get_manager_assertion_verifier().verify_runtime_command(
            assertion,
            action=action,
        )
    except ManagerAssertionConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.error_code},
        ) from exc
    except ManagerAssertionInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.error_code},
        ) from exc


def _manager_command_action(
    path: str,
    *,
    method: str | None = None,
) -> str | None:
    normalized = path.rstrip("/")
    if normalized.startswith("/api/v1"):
        normalized = normalized.removeprefix("/api/v1")
    if normalized == "/internal/worktree/sync-gitignore":
        return "worktree.sync"
    if normalized.startswith("/internal/settings/"):
        return "settings.sync"
    if normalized in {"/internal/health", "/internal/setup/status"}:
        return "runtime.inspect"
    if normalized == "/internal/marketplace/plugins/install":
        return "marketplace.execute" if method == "POST" else None
    if normalized == "/internal/marketplace/user-copies/preflight":
        return "marketplace.inspect" if method == "POST" else None
    if normalized == "/internal/marketplace/user-copies/apply":
        return "marketplace.execute" if method == "POST" else None
    if normalized.startswith("/internal/automation/"):
        return "automation.control"
    return None


def get_internal_service() -> InternalService:
    """Get Internal Service instance"""
    return InternalService()


__all__ = [
    "verify_manager_assertion",
    "get_internal_service",
]
