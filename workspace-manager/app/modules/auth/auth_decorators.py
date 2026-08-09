"""Authentication request-state helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request, status


def get_current_user_id(request: Request) -> str:
    """Get current local user ID from request.state."""

    user_id = getattr(request.state, "user_id", None)
    if not isinstance(user_id, str) or not user_id:
        translate = getattr(request.state, "translate", None)
        detail = (
            translate("auth.unauthenticated")
            if callable(translate)
            else "auth.unauthenticated"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
    return user_id
