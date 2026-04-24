"""模板安装、导入、导出与编译预览路由"""

import logging
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.models import CanonicalTarget, InstallPlan
from app.models.template_install import (
    TemplateInstallRequest,
    TemplateInstallResponse,
)
from app.services.template_canonical_service import CanonicalTemplateValidationError
from app.services.template_compiler_service import TemplateCompilerService
from app.services.template_install_service import TemplateInstallError, TemplateInstallService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)
router = APIRouter()


def _translate_template_install_error(translate, code: str, params: dict | None = None) -> str:
    params = params or {}
    if code == "TEMPLATE_INSTALL_WORKSPACE_NOT_FOUND":
        return translate("templates.install.workspace_not_found", workspace_id=params.get("workspace_id", ""))
    if code == "TEMPLATE_INSTALL_WORKSPACE_NOT_RUNNING":
        return translate("templates.install.workspace_not_running", workspace_id=params.get("workspace_id", ""))
    if code == "TEMPLATE_INSTALL_TEMPLATE_NOT_FOUND":
        return translate("templates.install.template_not_found", template_id=params.get("template_id", ""))
    if code == "TEMPLATE_INSTALL_RUNTIME_URL_MISSING":
        return translate("templates.install.workspace_runtime_url_missing", workspace_id=params.get("workspace_id", ""))
    if code == "TEMPLATE_INSTALL_RUNTIME_HTTP_ERROR":
        return translate(
            "templates.install.runtime_http_error",
            status_code=params.get("status_code", ""),
            response_text=params.get("response_text", ""),
        )
    if code == "TEMPLATE_INSTALL_RUNTIME_CONNECTION_ERROR":
        return translate("templates.install.runtime_connection_error_simple")
    return translate("templates.install_failed_simple")


def _translate_template_import_value_error(translate, error: str) -> str:
    if "ZIP 檔案已損壞或格式不正確" in error:
        return translate("templates.import.invalid_archive")
    if "缺少 .claude-plugin/manifest.json" in error:
        return translate("templates.import.missing_package_manifest")
    if "manifest.json 不是合法的 JSON" in error:
        return translate("templates.import.invalid_package_manifest")
    if "manifest.json 缺少 id 欄位" in error:
        return translate("templates.import.missing_package_manifest_id")
    if "manifest.json 的 id 格式不合法" in error:
        return translate("templates.import.invalid_package_manifest_id_format")
    if error.startswith("模板 '") and error.endswith("' 已存在，請使用覆蓋模式"):
        template_id = error[len("模板 '"):].split("' 已存在，請使用覆蓋模式", 1)[0]
        return translate("templates.import.already_exists", template_id=template_id)
    if "模板 package manifest 無效" in error:
        return translate("templates.import.invalid_package_manifest_metadata")
    return translate("templates.import_failed")


def _translate_template_install_generic_error(translate) -> str:
    return translate("templates.install_failed_simple")


def _translate_template_preview_generic_error(translate) -> str:
    return translate("templates.preview_failed")


def _translate_template_preview_validation_error(translate, error: str) -> str:
    if "Missing template.yaml" in error:
        return translate("templates.preview_missing_template_yaml")
    if "Template root not found" in error:
        return translate("templates.preview_template_root_not_found")
    return translate("templates.preview_invalid_canonical_template")


def get_template_service(db: Session = Depends(get_db)) -> TemplateService:
    """取得模板服務實例"""
    return TemplateService(db)


def get_template_install_service(db: Session = Depends(get_db)) -> TemplateInstallService:
    """取得模板安裝服務實例"""
    return TemplateInstallService(db)


def get_template_compiler_service(db: Session = Depends(get_db)) -> TemplateCompilerService:
    """取得模板編譯服務實例"""
    return TemplateCompilerService(db)


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
    - AGENTS.md / 指令文件
    - Commands
    - Agents
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
            message=translate("templates.install_success", template_name=template.name),
            templateId=payload.template_id,
            templateName=template.name,
            workspaceId=payload.workspace_id,
            results=result.get("results")
        )

    except TemplateInstallError as e:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
                if getattr(e, "code", "").startswith("TEMPLATE_INSTALL_WORKSPACE_")
                or getattr(e, "code", "") == "TEMPLATE_INSTALL_TEMPLATE_NOT_FOUND"
                else status.HTTP_502_BAD_GATEWAY
            ),
            detail=_translate_template_install_error(
                request.state.translate,
                getattr(e, "code", "TEMPLATE_INSTALL_FAILED"),
                getattr(e, "params", {}),
            )
        )
    except Exception as e:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_template_install_generic_error(translate)
        )


@router.get(
    "/{template_id}/compile-preview",
    response_model=InstallPlan,
    summary="取得模板目標編譯預覽",
    responses=build_responses(401, 404, 422, 500),
)
async def get_template_compile_preview(
    request: Request,
    template_id: str,
    target: CanonicalTarget = Query(..., description="編譯目標 CLI"),
    current_user_id: str = Depends(get_current_user_id),
    compiler_service: TemplateCompilerService = Depends(get_template_compiler_service),
    template_service: TemplateService = Depends(get_template_service),
) -> InstallPlan:
    """回傳指定模板在目標 CLI 下的編譯預覽結果。"""
    translate = request.state.translate
    template = template_service._get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found"),
        )

    try:
        return compiler_service.compile_template(template_id, target.value)
    except CanonicalTemplateValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_translate_template_preview_validation_error(translate, str(e)),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_template_preview_generic_error(translate),
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
    target: CanonicalTarget | None = Query(default=None, description="匯出目標 CLI"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
    compiler_service: TemplateCompilerService = Depends(get_template_compiler_service),
):
    """匯出模板為 target-specific ZIP 檔案。"""
    translate = request.state.translate
    template = service.get(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.export_not_found", template_id=template_id)
        )

    export_target = target or CanonicalTarget(template.cliType)
    try:
        plan = compiler_service.compile_template(template_id, export_target.value)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_template_preview_generic_error(translate),
        )

    temp_dir = Path(tempfile.mkdtemp())
    zip_path = temp_dir / f"{template_id}-{export_target.value}.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for compiled_file in plan.files:
                zipf.writestr(compiled_file.path, compiled_file.content)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("templates.export_failed"),
        )

    return FileResponse(
        path=str(zip_path),
        filename=f"{template_id}-{export_target.value}.zip",
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{template_id}-{export_target.value}.zip"'
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
    - 子目錄中必須包含 .claude-plugin/manifest.json
    - manifest.json 中的 id 必須與目錄名稱一致
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
            detail=_translate_template_import_value_error(translate, str(e))
        )

    return {
        "success": True,
        "message": translate("templates.import_success"),
        "template": template.model_dump()
    }


__all__ = ["router"]
