"""
ContainerImage API Route

Provides query APIs for ContainerImage configuration
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ConfigDict

from app.core.openapi import build_responses
from app.services.container_image_service import (
    ContainerImage,
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
    default_image_id: str = Field(..., alias="defaultImageId", description="Default Image ID")
    images: List[ContainerImageResponse] = Field(..., description="Image list")

    model_config = ConfigDict(populate_by_name=True)


@router.get(
    "",
    response_model=ContainerImagesListResponse,
    summary="List available ContainerImages",
    responses=build_responses(500),
)
def list_container_images(
    active_only: bool = True,
    service: ContainerImageService = Depends(get_container_image_service),
) -> ContainerImagesListResponse:
    """
    Get all available ContainerImages

    Args:
        active_only: Whether to return only enabled images (default is True)

    Returns:
        List of ContainerImages
    """
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
    responses=build_responses(404, 500),
)
def get_container_image(
    image_id: str,
    request: Request,
    service: ContainerImageService = Depends(get_container_image_service),
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
    image = service.get_image_by_id(image_id)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("container.image_not_found", image_id=image_id)
        )

    return ContainerImageResponse.model_validate(image)


@router.post(
    "/reload",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reload ContainerImage settings",
    responses=build_responses(500),
)
def reload_container_images(
    service: ContainerImageService = Depends(get_container_image_service),
) -> None:
    """
    Reload ContainerImage configuration

    Used to reload after modifying configuration files without restarting the service
    """
    service.reload_config()
