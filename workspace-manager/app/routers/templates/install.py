"""模板安装、导入、导出路由"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.models.template_install import (
    TemplateInstallRequest,
    TemplateInstallResponse,
)
from app.services.template_install_service import TemplateInstallError, TemplateInstallService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_template_service(db: Session = Depends(get_db)) -> TemplateService:
    """取得模板服務實例"""
    return TemplateService(db)


def get_template_install_service(db: Session = Depends(get_db)) -> TemplateInstallService:
    """取得模板安裝服務實例"""
    return TemplateInstallService(db)


@router.post(
    "/install",
    response_model=TemplateInstallResponse,
    summary="安裝模板到 Workspace",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def install_template(
    request: Request,
    payload: TemplateInstallRequest,
    current_user_id: str = Depends(get_current_user_id),
    install_service: TemplateInstallService = Depends(get_template_install_service),
    template_service: TemplateService = Depends(get_template_service)
) -> TemplateInstallResponse:
    """
    將模板配置安裝到指定的 workspace

    安裝內容包括：
    - Claude.md
    - Slash Commands
    - Subagents
    - MCP Servers
    - Hooks
    - Scripts
    """
    try:
        translate = request.state.translate
        # 驗證模板是否存在
        template = template_service._get_template(payload.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("templates.install_not_found", template_id=payload.template_id)
            )

        # 執行安裝
        result = await install_service.install_template_to_workspace(
            workspace_id=payload.workspace_id,
            template_id=payload.template_id
        )

        # 轉換結果格式
        return TemplateInstallResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            templateId=payload.template_id,
            templateName=template.name,
            workspaceId=payload.workspace_id,
            results=result.get("results")
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except TemplateInstallError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("templates.install_failed", error=str(e))
        )


@router.get(
    "/{template_id}/export",
    summary="匯出模板",
    responses={
        200: {"description": "成功匯出模板 ZIP 檔案。"},
        **build_responses(401, 404, 500),
    },
)
async def export_template(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
):
    """匯出模板為 ZIP 檔案"""
    zip_path = service.export_template(template_id)
    translate = request.state.translate

    if not zip_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.export_not_found", template_id=template_id)
        )

    return FileResponse(
        path=str(zip_path),
        filename=f"{template_id}.zip",
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{template_id}.zip"'
        }
    )


@router.post(
    "/import",
    summary="匯入模板",
    responses=build_responses(400, 401, 422, 500),
)
async def import_template(
    request: Request,
    file: UploadFile = File(..., description="模板 ZIP 檔案"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
):
    """
    匯入模板 ZIP 檔案

    ZIP 檔案結構要求:
    - 必須包含一個 template_id 子目錄
    - 子目錄中必須包含 marketplace.json
    - marketplace.json 中的 id 必須與目錄名稱一致
    - template_id 不能與現有模板重複
    """
    translate = request.state.translate
    # 檢查檔案類型
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("templates.import_invalid_format")
        )

    try:
        template = await service.import_template(file)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return {
        "success": True,
        "message": translate("templates.import_success"),
        "template": template.model_dump()
    }


__all__ = ["router"]
