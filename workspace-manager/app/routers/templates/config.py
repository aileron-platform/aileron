"""模板配置管理路由（MCP、Hooks、Marketplace）"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.models import (
    HooksConfigResponse,
    HooksConfigUpdateRequest,
    MarketplaceConfig,
    MarketplaceConfigResponse,
    MarketplaceConfigUpdateRequest,
    McpConfigResponse,
    McpConfigUpdateRequest,
)
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_template_service(db: Session = Depends(get_db)) -> TemplateService:
    """取得模板服務實例"""
    return TemplateService(db)


# ============ MCP 配置管理 ============


@router.get(
    "/{template_id}/mcp",
    response_model=McpConfigResponse,
    summary="取得 MCP 配置",
    responses=build_responses(401, 404, 500),
)
async def get_mcp_config(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> McpConfigResponse:
    """取得模板的 MCP 配置"""
    config = service.get_mcp_config(template_id)
    if not config:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return config


@router.put(
    "/{template_id}/mcp",
    response_model=McpConfigResponse,
    summary="更新 MCP 配置",
    responses=build_responses(401, 404, 422, 500),
)
async def update_mcp_config(
    request: Request,
    template_id: str,
    payload: McpConfigUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> McpConfigResponse:
    """更新模板的 MCP 配置"""
    config = service.update_mcp_config(template_id, payload)
    if not config:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return config


# ============ Hooks 配置管理 ============


@router.get(
    "/{template_id}/hooks",
    response_model=HooksConfigResponse,
    summary="取得 Hooks 配置",
    responses=build_responses(401, 404, 500),
)
async def get_hooks_config(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> HooksConfigResponse:
    """取得模板的 Hooks 配置"""
    config = service.get_hooks_config(template_id)
    if not config:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return config


@router.put(
    "/{template_id}/hooks",
    response_model=HooksConfigResponse,
    summary="更新 Hooks 配置",
    responses=build_responses(401, 404, 422, 500),
)
async def update_hooks_config(
    request: Request,
    template_id: str,
    payload: HooksConfigUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> HooksConfigResponse:
    """更新模板的 Hooks 配置"""
    config = service.update_hooks_config(template_id, payload)
    if not config:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return config


# ============ Marketplace 配置管理 ============


@router.get(
    "/marketplace/config",
    response_model=MarketplaceConfigResponse,
    summary="取得 Marketplace 配置",
    responses=build_responses(401, 500),
)
async def get_marketplace_config(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
):
    """取得模板中心的 Marketplace 配置"""
    try:
        translate = request.state.translate
        config = service.get_marketplace_config()
        return MarketplaceConfigResponse(
            success=True,
            data=config,
            message=translate("templates.marketplace_config_get_success")
        )
    except Exception as e:
        logger.error(f"取得 Marketplace 配置失敗: {e}")
        translate = request.state.translate
        return MarketplaceConfigResponse(
            success=False,
            error=str(e),
            message=translate("templates.marketplace_config_get_failed")
        )


@router.put(
    "/marketplace/config",
    response_model=MarketplaceConfigResponse,
    summary="更新 Marketplace 配置",
    responses=build_responses(401, 422, 500),
)
async def update_marketplace_config(
    request: Request,
    payload: MarketplaceConfigUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
):
    """更新模板中心的 Marketplace 配置"""
    try:
        translate = request.state.translate
        config = MarketplaceConfig(
            name=payload.name,
            owner=payload.owner,
            metadata=payload.metadata
        )
        updated_config = service.update_marketplace_config(config)
        return MarketplaceConfigResponse(
            success=True,
            data=updated_config,
            message=translate("templates.marketplace_config_update_success")
        )
    except Exception as e:
        logger.error(f"更新 Marketplace 配置失敗: {e}")
        translate = request.state.translate
        return MarketplaceConfigResponse(
            success=False,
            error=str(e),
            message=translate("templates.marketplace_config_update_failed")
        )


__all__ = ["router"]
