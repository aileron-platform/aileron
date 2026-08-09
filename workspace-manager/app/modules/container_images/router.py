"""
ContainerImage API Route

Provides query APIs for ContainerImage configuration
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.api_error import authorization_error_detail
from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.container_images.catalog import (
    ContainerImageService,
    get_container_image_service,
)

router = APIRouter(prefix="/container-images", tags=["container-images"])


class ContainerImageResponse(BaseModel):
    """ContainerImageResponse"""

    id: str = Field(..., description="Image unique identifier")
    name: str = Field(..., description="Image display name")
    description: str = Field(..., description="Image description")
    icon: str = Field(..., description="Image icon")
    image: str = Field(..., description="Docker Image name")
    tags: List[str] = Field(default_factory=list, description="Image tags")
    features: List[str] = Field(default_factory=list, description="Image feature list")
    recommended: bool = Field(..., description="Whether this is a recommended image")
    active: bool = Field(..., description="Is active")

    model_config = ConfigDict(from_attributes=True)


class ContainerImagesListResponse(BaseModel):
    """ContainerImage list response"""

    default_image_id: str = Field(
        ..., alias="defaultImageId", description="Default Image ID"
    )
    images: List[ContainerImageResponse] = Field(..., description="Image list")

    model_config = ConfigDict(populate_by_name=True)


def _require_platform_operation(
    request: Request,
    db: Session,
    *,
    actor: AuthorizationActor,
    operation: OperationId,
) -> None:
    try:
        AuthorizationOperationPolicy(db).require_platform_operation(
            actor,
            operation,
        )
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("access_denied"),
            ),
        ) from exc


@router.get(
    "",
    response_model=ContainerImagesListResponse,
    summary="List available ContainerImages",
    responses=build_responses(401, 403, 500),
)
def list_container_images(
    request: Request,
    active_only: bool = True,
    service: ContainerImageService = Depends(get_container_image_service),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    db: Session = Depends(get_db),
) -> ContainerImagesListResponse:
    """
    Get all available ContainerImages

    Args:
        active_only: Whether to return only enabled images (default is True)

    Returns:
        List of ContainerImages
    """
    _require_platform_operation(
        request,
        db,
        actor=actor,
        operation=OperationId.WORKSPACE_COLLECTION_READ,
    )
    images = service.get_all_images(active_only=active_only)
    default_image = service.get_default_image()

    return ContainerImagesListResponse(
        defaultImageId=default_image.id,
        images=[ContainerImageResponse.model_validate(img) for img in images],
    )


@router.get(
    "/{image_id}",
    response_model=ContainerImageResponse,
    summary="Get ContainerImage details",
    responses=build_responses(401, 403, 404, 500),
)
def get_container_image(
    image_id: str,
    request: Request,
    service: ContainerImageService = Depends(get_container_image_service),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    db: Session = Depends(get_db),
) -> ContainerImageResponse:
    """
    Get ContainerImage details by ID

    Args:
        image_id: Image ID

    Returns:
        ContainerImage details

    Raises:
        HTTPException: If image does not exist
    """
    _require_platform_operation(
        request,
        db,
        actor=actor,
        operation=OperationId.WORKSPACE_COLLECTION_READ,
    )
    image = service.get_image_by_id(image_id)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate(
                "container.image_not_found", image_id=image_id
            ),
        )

    return ContainerImageResponse.model_validate(image)


@router.post(
    "/reload",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reload ContainerImage settings",
    responses=build_responses(401, 403, 500),
)
def reload_container_images(
    request: Request,
    service: ContainerImageService = Depends(get_container_image_service),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    db: Session = Depends(get_db),
) -> None:
    """
    Reload ContainerImage configuration

    Used to reload after modifying configuration files without restarting the service
    """
    _require_platform_operation(
        request,
        db,
        actor=actor,
        operation=OperationId.USER_MANAGEMENT_MANAGE,
    )
    service.reload_config()
