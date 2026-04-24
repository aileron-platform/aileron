"""模板配置管理路由（MCP、Hooks）"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.models import (
    HooksConfigResponse,
    HooksConfigUpdateRequest,
    McpConfigResponse,
    McpConfigUpdateRequest,
)
from app.services.template_service import TemplateService
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


__all__ = ["router"]
