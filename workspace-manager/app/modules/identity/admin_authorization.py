"""Admin authorization dependency."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.api_error import authorization_error_detail
from app.db import models as db_models
from app.db.database import get_db
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)


def require_admin_user(
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    db: Session = Depends(get_db),
) -> db_models.User:
    """FastAPI dependency for admin APIs."""

    try:
        AuthorizationOperationPolicy(db).require_platform_operation(
            actor,
            OperationId.USER_MANAGEMENT_MANAGE,
        )
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("access_denied"),
            ),
        ) from exc
    user = db.get(db_models.User, actor.user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail=authorization_error_detail(
                "PLATFORM_AUTHORIZATION_DENIED",
                request.state.translate("auth.unauthenticated"),
            ),
        )
    return user
