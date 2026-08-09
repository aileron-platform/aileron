"""Shared Runtime-to-Manager identity dependency."""

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.workspace.runtime.control_token import verify_runtime_control_token


def require_internal_runtime_identity(
    request: Request,
    *,
    workspace_id: str,
    db: Session,
) -> db_models.Workspace:
    """Validate the active Runtime generation and return its Workspace."""

    token = getattr(request.state, "runtime_control_token", None)
    if not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "internal_auth_required"},
        )
    if getattr(request.state, "runtime_workspace_id", None) != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "workspace_identity_mismatch"},
        )
    workspace = db.get(db_models.Workspace, workspace_id)
    if (
        workspace is None
        or workspace.runtime_control_instance_id
        != getattr(request.state, "runtime_instance_id", None)
        or workspace.runtime_status not in {"starting", "running", "restarting"}
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "runtime_instance_mismatch"},
        )
    if not verify_runtime_control_token(token, workspace.runtime_control_token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "internal_auth_required"},
        )
    return workspace


__all__ = ["require_internal_runtime_identity"]
