"""Admin resource statistics routes."""

from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.api_error import authorization_error_detail
from app.db.database import get_db
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import AuthorizationOperationError
from app.modules.platform_resource_capacity.errors import PlatformResourceError

from .models import (
    CapacityTrendResponse,
    PlatformResourceSummaryResponse,
    ResourceTrendResponse,
)
from .projection import PlatformResourceAnalytics

router = APIRouter(tags=["platform-resource-analytics"])


def get_platform_resource_analytics(
    db: Session = Depends(get_db),
) -> PlatformResourceAnalytics:
    return PlatformResourceAnalytics(db)


def _resource_type(segment: str) -> Literal["workspace", "knowledge_base"]:
    if segment == "workspaces":
        return "workspace"
    if segment == "knowledge-bases":
        return "knowledge_base"
    raise PlatformResourceError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)


@router.get(
    "/platform-resources/{segment}/statistics/summary",
    response_model=PlatformResourceSummaryResponse,
)
def get_platform_resource_summary(
    segment: Literal["workspaces", "knowledge-bases"],
    request: Request,
    range_value: Literal["7d", "30d", "90d"] = Query("30d", alias="range"),
    refresh: bool = Query(False),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    analytics: PlatformResourceAnalytics = Depends(
        get_platform_resource_analytics
    ),
) -> PlatformResourceSummaryResponse:
    try:
        return analytics.get_summary(
            actor=actor,
            resource_type=_resource_type(segment),
            range_value=range_value,
            refresh=refresh,
        )
    except (AuthorizationOperationError, PlatformResourceError) as exc:
        _raise_error(request, exc)


@router.get(
    "/platform-resources/{segment}/statistics/resource-trend",
    response_model=ResourceTrendResponse,
)
def get_platform_resource_trend(
    segment: Literal["workspaces", "knowledge-bases"],
    request: Request,
    range_value: Literal["7d", "30d", "90d"] = Query("30d", alias="range"),
    refresh: bool = Query(False),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    analytics: PlatformResourceAnalytics = Depends(
        get_platform_resource_analytics
    ),
) -> ResourceTrendResponse:
    try:
        return analytics.get_resource_trend(
            actor=actor,
            resource_type=_resource_type(segment),
            range_value=range_value,
            refresh=refresh,
        )
    except (AuthorizationOperationError, PlatformResourceError) as exc:
        _raise_error(request, exc)


@router.get(
    "/platform-resources/{segment}/statistics/capacity-trend",
    response_model=CapacityTrendResponse,
)
def get_platform_resource_capacity_trend(
    segment: Literal["workspaces", "knowledge-bases"],
    request: Request,
    range_value: Literal["7d", "30d", "90d"] = Query("30d", alias="range"),
    refresh: bool = Query(False),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    analytics: PlatformResourceAnalytics = Depends(
        get_platform_resource_analytics
    ),
) -> CapacityTrendResponse:
    try:
        return analytics.get_capacity_trend(
            actor=actor,
            resource_type=_resource_type(segment),
            range_value=range_value,
            refresh=refresh,
        )
    except (AuthorizationOperationError, PlatformResourceError) as exc:
        _raise_error(request, exc)


def _raise_error(
    request: Request,
    error: AuthorizationOperationError | PlatformResourceError,
) -> NoReturn:
    message_key = {
        "PLATFORM_AUTHORIZATION_DENIED": "platform_resources.permission_denied",
        "PLATFORM_RESOURCE_NOT_FOUND": "platform_resources.not_found",
    }.get(error.error_code, "platform_resources.invalid_request")
    raise HTTPException(
        status_code=error.http_status,
        detail=authorization_error_detail(
            error.error_code,
            request.state.translate(message_key),
            details={"correlationId": request.state.correlation_id},
        ),
    ) from error
