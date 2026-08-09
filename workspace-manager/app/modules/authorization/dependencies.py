"""FastAPI dependencies for request-scoped authorization."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.core.api_error import authorization_error_detail
from app.modules.authorization.actor import AuthorizationActor


def get_authorization_actor(
    request: Request,
) -> AuthorizationActor:
    """Return the actor established by Manager request authentication."""

    actor = getattr(request.state, "authorization_actor", None)
    if not isinstance(actor, AuthorizationActor):
        translate = getattr(request.state, "translate", None)
        message = (
            translate("auth.unauthenticated")
            if callable(translate)
            else "auth.unauthenticated"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=authorization_error_detail(
                "MANAGER_SESSION_REQUIRED",
                message,
            ),
        )
    return actor


__all__ = ["get_authorization_actor"]
