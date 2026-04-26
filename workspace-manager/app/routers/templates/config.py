"""Template configuration management routes (MCP, Hooks)"""

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
    """Get template service instance"""
    return TemplateService(db)


# ============ MCP configuration management ============


@router.get(
    "/{template_id}/mcp",
    response_model=McpConfigResponse,
    summary="Get MCP Configuration",
    responses=build_responses(401, 404, 500),
)
async def get_mcp_config(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> McpConfigResponse:
    """Get template MCP configuration"""
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
    summary="Update MCP Configuration",
    responses=build_responses(401, 404, 422, 500),
)
async def update_mcp_config(
    request: Request,
    template_id: str,
    payload: McpConfigUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> McpConfigResponse:
    """Update template MCP configuration"""
    config = service.update_mcp_config(template_id, payload)
    if not config:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return config


# ============ Hooks configuration management =============


@router.get(
    "/{template_id}/hooks",
    response_model=HooksConfigResponse,
    summary="Get Hooks Configuration",
    responses=build_responses(401, 404, 500),
)
async def get_hooks_config(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> HooksConfigResponse:
    """Get template's hooks configuration"""
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
    summary="Update Hooks Configuration",
    responses=build_responses(401, 404, 422, 500),
)
async def update_hooks_config(
    request: Request,
    template_id: str,
    payload: HooksConfigUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> HooksConfigResponse:
    """Update template's hooks configuration"""
    config = service.update_hooks_config(template_id, payload)
    if not config:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return config


__all__ = ["router"]
