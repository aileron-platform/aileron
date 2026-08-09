"""Internal Runtime telemetry ingestion route."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.internal_runtime import require_internal_runtime_identity
from app.modules.platform_resource_capacity.errors import PlatformResourceError

from .ingestion import PlatformResourceTelemetryIngestion, RuntimeTelemetryIdentity
from .models import RuntimeTelemetryBatch, TelemetryIngestResponse

router = APIRouter(prefix="/internal/workspaces", tags=["internal-resource-telemetry"])


@router.post(
    "/{workspace_id}/resource-telemetry/batches",
    response_model=TelemetryIngestResponse,
)
def ingest_runtime_resource_telemetry(
    workspace_id: str,
    payload: RuntimeTelemetryBatch,
    request: Request,
    workspace_header: str = Header(alias="X-Workspace-ID"),
    db: Session = Depends(get_db),
) -> TelemetryIngestResponse:
    workspace = require_internal_runtime_identity(
        request, workspace_id=workspace_id, db=db
    )
    try:
        return PlatformResourceTelemetryIngestion(db).ingest(
            identity=RuntimeTelemetryIdentity(
                route_workspace_id=workspace_id,
                header_workspace_id=workspace_header,
                authenticated_runtime_instance_id=getattr(
                    request.state, "runtime_instance_id", None
                ),
                expected_runtime_instance_id=str(workspace.runtime_control_instance_id),
            ),
            batch=payload,
        )
    except PlatformResourceError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"code": exc.error_code},
        ) from exc


__all__ = ["router"]
