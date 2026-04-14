"""
容器映像 API 路由

提供容器映像配置的查詢 API
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
    """容器映像回應"""
    id: str = Field(..., description="映像唯一識別碼")
    name: str = Field(..., description="映像顯示名稱")
    description: str = Field(..., description="映像描述")
    icon: str = Field(..., description="映像圖示")
    image: str = Field(..., description="Docker 映像名稱")
    tags: List[str] = Field(default_factory=list, description="映像標籤")
    features: List[str] = Field(default_factory=list, description="映像特性列表")
    recommended: bool = Field(..., description="是否為推薦映像")
    active: bool = Field(..., description="是否啟用")

    model_config = ConfigDict(from_attributes=True)


class ContainerImagesListResponse(BaseModel):
    """容器映像列表回應"""
    default_image_id: str = Field(..., alias="defaultImageId", description="預設映像 ID")
    images: List[ContainerImageResponse] = Field(..., description="映像列表")

    model_config = ConfigDict(populate_by_name=True)


@router.get(
    "",
    response_model=ContainerImagesListResponse,
    summary="列出可用容器映像",
    responses=build_responses(500),
)
def list_container_images(
    active_only: bool = True,
    service: ContainerImageService = Depends(get_container_image_service),
) -> ContainerImagesListResponse:
    """
    取得所有可用的容器映像

    Args:
        active_only: 是否只返回啟用的映像（預設為 True）

    Returns:
        容器映像列表
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
    summary="取得容器映像詳情",
    responses=build_responses(404, 500),
)
def get_container_image(
    image_id: str,
    request: Request,
    service: ContainerImageService = Depends(get_container_image_service),
) -> ContainerImageResponse:
    """
    根據 ID 取得容器映像詳情

    Args:
        image_id: 映像 ID

    Returns:
        容器映像詳情

    Raises:
        HTTPException: 若映像不存在
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
    summary="重新載入容器映像設定",
    responses=build_responses(500),
)
def reload_container_images(
    service: ContainerImageService = Depends(get_container_image_service),
) -> None:
    """
    重新載入容器映像配置

    用於在修改配置檔後重新載入，無需重啟服務
    """
    service.reload_config()
