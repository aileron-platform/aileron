"""工作區 API"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from app.core.openapi import build_responses
from app.models import (
    KnowledgeBaseErrorResponse,
    WorkspaceCreateRequest,
    WorkspaceDetail,
    WorkspaceKnowledgeBaseAttachment,
    WorkspaceKnowledgeBaseAttachmentCreateRequest,
    WorkspaceKnowledgeBaseAttachmentListResponse,
    WorkspaceKnowledgeBaseAttachmentUpdateRequest,
    WorkspaceListResponse,
    WorkspaceShare,
    WorkspaceShareCreateRequest,
    WorkspaceShareListResponse,
    WorkspaceShareUpdateRequest,
    WorkspaceUpdateRequest,
    WorkspaceRuntimeLogEntry,
)
from app.services import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    get_knowledge_base_attachment_service,
    get_runtime_provision_service,
    get_workspace_service,
)
from app.services.knowledge_base_attachment_service import KnowledgeBaseAttachmentService
from app.services.knowledge_base_attachment_service import (
    KB_ALREADY_ATTACHED_MESSAGE,
    KB_ATTACHMENT_NOT_FOUND_MESSAGE,
    KB_MOUNT_ALIAS_CONFLICT_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
)
from app.services.knowledge_base_service import (
    KB_ACCESS_DENIED_MESSAGE,
    KB_NOT_FOUND_MESSAGE,
    KB_PERMISSION_DENIED_MESSAGE,
)
from app.services.runtime_provision_service import (
    RuntimeProvisionService,
    run_runtime_provision_task,
)
from app.services.workspace_custom_resource_service import (
    run_apply_workspace_custom_resource_task,
)
from app.services.runtime_sync_service import RuntimeSyncService
from app.services.workspace_service import WorkspaceService
from app.services.workspace_service import (
    WORKSPACE_ACCESS_DENIED_MESSAGE,
    WORKSPACE_INVALID_NAMESPACE_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
    WORKSPACE_OWNER_NOT_FOUND_MESSAGE,
    WORKSPACE_PORT_MAPPINGS_UNSUPPORTED_MESSAGE,
    WORKSPACE_RUNTIME_RESOURCES_UNSUPPORTED_MESSAGE,
    WORKSPACE_SHARE_CONFLICT_MESSAGE,
    WORKSPACE_SHARE_NOT_FOUND_MESSAGE,
    WORKSPACE_SHARE_OWNER_FORBIDDEN_MESSAGE,
    WORKSPACE_SHARE_TARGET_NOT_FOUND_MESSAGE,
    WorkspaceAccessDeniedError,
)
from app.db.database import SessionLocal
from app.services.workspace_lifecycle_service import (
    run_delete_workspace_task,
    run_restart_workspace_task,
    run_restart_browser_task,
    run_restart_nextjs_task,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_WORKSPACE_KB_ERROR_DESCRIPTIONS = {
    400: "工作區 knowledge base 請求不合法，例如 payload 格式錯誤。",
    403: "目前使用者沒有對工作區或知識庫掛載的操作權限。",
    404: "指定工作區、知識庫或掛載不存在。",
    409: "工作區 knowledge base 狀態衝突，例如重複掛載或掛載別名衝突。",
}

_WORKSPACE_SHARE_ERROR_DESCRIPTIONS = {
    400: "工作區分享請求不合法，例如不可分享給擁有者。",
    403: "目前使用者沒有管理工作區分享的權限。",
    404: "指定工作區、分享目標或工作區分享不存在。",
    409: "工作區分享狀態衝突，例如重複分享同一位使用者。",
}

_WORKSPACE_SHARE_ERROR_EXAMPLES = {
    400: {
        "shareOwnerForbidden": {
            "summary": "不可分享給工作區擁有者",
            "value": {
                "detail": {
                    "code": "WORKSPACE_INVALID_SHARE_TARGET",
                    "message": "不可將工作區分享給擁有者",
                    "details": {"resource": "workspace_share"},
                }
            },
        }
    },
    404: {
        "shareNotFound": {
            "summary": "指定的工作區分享不存在",
            "value": {
                "detail": {
                    "code": "WORKSPACE_SHARE_NOT_FOUND",
                    "message": "工作區分享不存在",
                    "details": {"resource": "workspace_share"},
                }
            },
        }
    },
    409: {
        "shareConflict": {
            "summary": "重複分享同一位使用者",
            "value": {
                "detail": {
                    "code": "WORKSPACE_SHARE_CONFLICT",
                    "message": "工作區分享已存在",
                    "details": {"resource": "workspace_share"},
                }
            },
        }
    },
}

_WORKSPACE_KB_ERROR_EXAMPLES = {
    404: {
        "attachmentNotFound": {
            "summary": "指定的知識庫掛載不存在",
            "value": {
                "detail": {
                    "code": "KB_ATTACHMENT_NOT_FOUND",
                    "message": "知識庫掛載不存在",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        }
    },
    409: {
        "duplicateAttachment": {
            "summary": "重複掛載同一個知識庫",
            "value": {
                "detail": {
                    "code": "KB_ALREADY_ATTACHED",
                    "message": "知識庫已掛載到此工作區",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "aliasConflict": {
            "summary": "掛載別名衝突",
            "value": {
                "detail": {
                    "code": "KB_MOUNT_ALIAS_CONFLICT",
                    "message": "知識庫掛載別名已存在",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
    },
}


def _build_workspace_kb_responses(*status_codes: int) -> dict[int, dict]:
    return build_responses(
        *status_codes,
        model=KnowledgeBaseErrorResponse,
        descriptions=_WORKSPACE_KB_ERROR_DESCRIPTIONS,
        examples={
            status_code: _WORKSPACE_KB_ERROR_EXAMPLES[status_code]
            for status_code in status_codes
            if status_code in _WORKSPACE_KB_ERROR_EXAMPLES
        },
    )


def _build_workspace_share_responses(*status_codes: int) -> dict[int, dict]:
    return build_responses(
        *status_codes,
        model=KnowledgeBaseErrorResponse,
        descriptions=_WORKSPACE_SHARE_ERROR_DESCRIPTIONS,
        examples={
            status_code: _WORKSPACE_SHARE_ERROR_EXAMPLES[status_code]
            for status_code in status_codes
            if status_code in _WORKSPACE_SHARE_ERROR_EXAMPLES
        },
    )


def _build_workspace_kb_error_detail(*, code: str, message: str, details: dict | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "details": details or {},
    }


def _translate_workspace_share_message(translate, message: str) -> str:
    mapping = {
        WORKSPACE_NOT_FOUND_MESSAGE: translate("workspace.not_found"),
        WORKSPACE_SHARE_TARGET_NOT_FOUND_MESSAGE: translate("workspace.share.target_not_found"),
        WORKSPACE_SHARE_OWNER_FORBIDDEN_MESSAGE: translate("workspace.share.owner_forbidden"),
        WORKSPACE_SHARE_CONFLICT_MESSAGE: translate("workspace.share.conflict"),
        WORKSPACE_SHARE_NOT_FOUND_MESSAGE: translate("workspace.share.not_found"),
    }
    return mapping.get(message, message)


def _workspace_share_error_detail(message: str, translate) -> dict:
    mapping = {
        WORKSPACE_NOT_FOUND_MESSAGE: ("WORKSPACE_NOT_FOUND", "workspace"),
        WORKSPACE_SHARE_TARGET_NOT_FOUND_MESSAGE: ("WORKSPACE_SHARE_TARGET_NOT_FOUND", "user"),
        WORKSPACE_SHARE_OWNER_FORBIDDEN_MESSAGE: ("WORKSPACE_INVALID_SHARE_TARGET", "workspace_share"),
        WORKSPACE_SHARE_CONFLICT_MESSAGE: ("WORKSPACE_SHARE_CONFLICT", "workspace_share"),
        WORKSPACE_SHARE_NOT_FOUND_MESSAGE: ("WORKSPACE_SHARE_NOT_FOUND", "workspace_share"),
    }
    code, resource = mapping.get(message, ("WORKSPACE_INVALID_REQUEST", "workspace_share"))
    return _build_workspace_kb_error_detail(
        code=code,
        message=_translate_workspace_share_message(translate, message),
        details={"resource": resource},
    )


def _translate_workspace_kb_message(translate, message: str) -> str:
    mapping = {
        WORKSPACE_NOT_FOUND_MESSAGE: translate("workspace.not_found"),
        KB_NOT_FOUND_MESSAGE: translate("knowledge_base.not_found"),
        KB_ATTACHMENT_NOT_FOUND_MESSAGE: translate("knowledge_base.attachment_not_found"),
        KB_ALREADY_ATTACHED_MESSAGE: translate("knowledge_base.already_attached"),
        KB_MOUNT_ALIAS_CONFLICT_MESSAGE: translate("knowledge_base.alias_conflict"),
        KB_ACCESS_DENIED_MESSAGE: translate("knowledge_base.access_denied"),
        KB_PERMISSION_DENIED_MESSAGE: translate("knowledge_base.permission_denied"),
    }
    return mapping.get(message, message)


def _translate_workspace_value_error(translate, message: str) -> str:
    if message == WORKSPACE_OWNER_NOT_FOUND_MESSAGE:
        return translate("workspace.owner_not_found")
    if message == WORKSPACE_RUNTIME_RESOURCES_UNSUPPORTED_MESSAGE:
        return translate("workspace.runtime_resources_unsupported")
    if message == WORKSPACE_PORT_MAPPINGS_UNSUPPORTED_MESSAGE:
        return translate("workspace.port_mappings_unsupported")
    if message.startswith(f"{WORKSPACE_INVALID_NAMESPACE_MESSAGE}: "):
        namespace = message.split(": ", 1)[1]
        return translate("workspace.invalid_namespace", namespace=namespace)
    return message


def _workspace_kb_not_found_detail(message: str, translate) -> dict:
    mapping = {
        WORKSPACE_NOT_FOUND_MESSAGE: ("WORKSPACE_NOT_FOUND", "workspace"),
        KB_NOT_FOUND_MESSAGE: ("KB_NOT_FOUND", "knowledge_base"),
        KB_ATTACHMENT_NOT_FOUND_MESSAGE: ("KB_ATTACHMENT_NOT_FOUND", "knowledge_base_attachment"),
    }
    code, resource = mapping.get(message, ("KB_NOT_FOUND", "knowledge_base"))
    return _build_workspace_kb_error_detail(
        code=code,
        message=_translate_workspace_kb_message(translate, message),
        details={"resource": resource},
    )


def _workspace_kb_conflict_detail(message: str, translate) -> dict:
    mapping = {
        KB_ALREADY_ATTACHED_MESSAGE: ("KB_ALREADY_ATTACHED", "knowledge_base_attachment"),
        KB_MOUNT_ALIAS_CONFLICT_MESSAGE: ("KB_MOUNT_ALIAS_CONFLICT", "knowledge_base_attachment"),
    }
    code, resource = mapping.get(message, ("KB_CONFLICT", "knowledge_base_attachment"))
    return _build_workspace_kb_error_detail(
        code=code,
        message=_translate_workspace_kb_message(translate, message),
        details={"resource": resource},
    )

_RUNTIME_LOG_STAGE_KEYS = {
    "queued": "workspace.runtime_log.queued",
    "provisioning": "workspace.runtime_log.provisioning",
    "preparing": "workspace.runtime_log.preparing",
    "provisioned": "workspace.runtime_log.provisioned",
    "browser_starting": "workspace.runtime_log.browser_starting",
    "browser_ready": "workspace.runtime_log.browser_ready",
    "nextjs_starting": "workspace.runtime_log.nextjs_starting",
    "nextjs_ready": "workspace.runtime_log.nextjs_ready",
    "completed": "workspace.runtime_log.completed",
    "browser_restarting": "workspace.runtime_log.browser_restarting",
    "browser_running": "workspace.runtime_log.browser_running",
    "nextjs_restarting": "workspace.runtime_log.nextjs_restarting",
    "nextjs_running": "workspace.runtime_log.nextjs_running",
}

_RUNTIME_LOG_EXACT_KEYS = {
    "沒有關聯的 Browser 容器": "workspace.runtime_log.browser_not_found",
    "No Browser container found for this workspace": "workspace.runtime_log.browser_not_found",
    "沒有關聯的 Next.js 容器": "workspace.runtime_log.nextjs_not_found",
    "No Next.js container found for this workspace": "workspace.runtime_log.nextjs_not_found",
}

_RUNTIME_LOG_PREFIX_KEYS = (
    ("Browser 容器啟動失敗: ", "workspace.runtime_log.browser_error"),
    ("Browser container startup failed: ", "workspace.runtime_log.browser_error"),
    ("Next.js 容器啟動失敗: ", "workspace.runtime_log.nextjs_error"),
    ("Next.js container startup failed: ", "workspace.runtime_log.nextjs_error"),
    ("重建失敗: ", "workspace.runtime_log.rebuild_error"),
    ("Rebuild failed: ", "workspace.runtime_log.rebuild_error"),
    ("已刪除目錄: ", "workspace.runtime_log.volume_removed"),
    ("Removed directory: ", "workspace.runtime_log.volume_removed"),
    ("刪除目錄失敗: ", "workspace.runtime_log.volume_error"),
    ("Failed to remove directory: ", "workspace.runtime_log.volume_error"),
)


def _translate_runtime_log_message(
    stage: str,
    message: str,
    translate,
) -> str:
    exact_key = _RUNTIME_LOG_EXACT_KEYS.get(message)
    if exact_key:
        return translate(exact_key)

    for prefix, key in _RUNTIME_LOG_PREFIX_KEYS:
        if message.startswith(prefix):
            detail = message[len(prefix):].strip()
            return translate(key, detail=detail)

    stage_key = _RUNTIME_LOG_STAGE_KEYS.get(stage)
    if stage_key:
        return translate(stage_key)

    return message


def _require_current_user_id(request: Request) -> str | None:
    if getattr(request.state, "internal_authenticated", False):
        return None

    current_user_id = getattr(request.state, "user_id", None)
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=request.state.translate("auth.unauthenticated"),
        )
    return current_user_id


@router.get(
    "/",
    response_model=WorkspaceListResponse,
    summary="列出工作區",
    responses=build_responses(401, 422, 500),
)
def list_workspaces(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceListResponse:
    current_user_id = _require_current_user_id(request)
    return service.list(
        page=page,
        page_size=page_size,
        current_user_id=current_user_id,
        status=status,
        search=search,
    )


@router.post(
    "/",
    response_model=WorkspaceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="建立工作區",
    responses=build_responses(400, 401, 422, 500),
)
def create_workspace(
    request: Request,
    payload: WorkspaceCreateRequest,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    try:
        current_user_id = _require_current_user_id(request)
        payload.owner_id = current_user_id

        workspace = service.create(payload)
        if workspace.provisioner == "kubernetes":
            background_tasks.add_task(run_apply_workspace_custom_resource_task, workspace.id)
        else:
            background_tasks.add_task(run_runtime_provision_task, workspace.id)
        return workspace
    except ValueError as exc:  # owner 不存在
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_workspace_value_error(request.state.translate, str(exc)),
        ) from exc


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
    summary="取得工作區詳情",
    responses=build_responses(404, 500),
)
def get_workspace(
    workspace_id: str,
    request: Request,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    current_user_id = _require_current_user_id(request)
    try:
        workspace = service.get(workspace_id, current_user_id=current_user_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found")
            )
        return workspace
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc


@router.get(
    "/{workspace_id}/runtime-logs",
    response_model=list[WorkspaceRuntimeLogEntry],
    summary="取得 Runtime 佈署日誌",
    responses=build_responses(422, 500),
)
def get_workspace_runtime_logs(
    request: Request,
    workspace_id: str,
    limit: int = Query(100, ge=1, le=500),
    stage: Optional[str] = Query(None),
    service: RuntimeProvisionService = Depends(get_runtime_provision_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceRuntimeLogEntry]:
    current_user_id = _require_current_user_id(request)
    try:
        workspace = workspace_service.get(workspace_id, current_user_id=current_user_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found")
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc

    logs = service.get_runtime_logs(workspace_id, limit=limit, stage=stage)
    if not logs:
        return []

    # 手動轉換資料庫物件到 Pydantic model
    result = []
    for log in logs:
        log_entry = WorkspaceRuntimeLogEntry(
            id=log.id,
            workspace_id=log.workspace_id,
            stage=log.stage,
            message=_translate_runtime_log_message(log.stage, log.message, request.state.translate),
            metadata=log.log_metadata,  # 映射 log_metadata 到 metadata
            created_at=log.created_at,
        )
        result.append(log_entry)

    return result


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
    summary="更新工作區",
    responses=build_responses(404, 422, 500),
)
async def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    current_user_id = _require_current_user_id(request)
    try:
        # 只有 firewall 配置變更需要額外同步到 workspace-runtime，其餘欄位由 manager 自行持久化。
        firewall_changed = payload.firewall is not None

        workspace = service.update(
            workspace_id,
            payload,
            current_user_id=current_user_id,
        )
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found")
            )

        # Docker workspace 的 firewall 透過 runtime internal API 套用。
        if firewall_changed and workspace.firewall and workspace.provisioner == "docker":
            background_tasks.add_task(
                _sync_firewall_to_runtime,
                workspace_id,
                workspace.firewall.model_dump(by_alias=True)
            )

        if workspace.provisioner == "kubernetes":
            background_tasks.add_task(run_apply_workspace_custom_resource_task, workspace.id)

        return workspace
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_workspace_value_error(request.state.translate, str(exc)),
        ) from exc


async def _sync_firewall_to_runtime(workspace_id: str, firewall_config: dict):
    """背景任務：同步防火牆設定到 workspace-runtime"""
    logger.info(f"開始背景同步防火牆設定 - workspace_id: {workspace_id}")

    db = SessionLocal()
    try:
        sync_service = RuntimeSyncService(db)
        result = await sync_service.sync_firewall_to_runtime(workspace_id, firewall_config)

        if result.get("success"):
            logger.info(f"防火牆設定同步成功 - workspace_id: {workspace_id}")
        else:
            logger.warning(f"防火牆設定同步跳過 - workspace_id: {workspace_id}, reason: {result.get('message')}")

    except Exception as e:
        logger.error(f"防火牆設定同步失敗 - workspace_id: {workspace_id}, error: {e}", exc_info=True)
    finally:
        db.close()


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="刪除工作區",
    responses=build_responses(404, 500),
)
def delete_workspace(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """刪除工作區

    此操作會在背景執行以下步驟：
    1. 停止並刪除 Docker container
    2. 刪除掛載的資料目錄
    3. 刪除資料庫中的 workspace 記錄

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID

    Raises:
        HTTPException: 當 workspace 不存在時
    """
    # 檢查 workspace 是否存在
    current_user_id = _require_current_user_id(request)
    try:
        workspace = service.get(workspace_id, current_user_id=current_user_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
            )

        if not service.mark_workspace_deleting(
            workspace_id,
            current_user_id=current_user_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=request.state.translate("workspace.deletion_failed")
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc

    # 加入背景任務
    background_tasks.add_task(run_delete_workspace_task, workspace_id)

    return {
        "message": request.state.translate("workspace.deletion_started"),
        "workspaceId": workspace_id,
        "status": "deleting"
    }


@router.post(
    "/{workspace_id}/rebuild",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重建工作區 Runtime",
    responses=build_responses(404, 500),
)
def rebuild_workspace(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """重啟工作區 Container

    此操作會在背景執行以下步驟：
    1. 重啟 Docker container
    2. 更新 workspace 狀態

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID

    Raises:
        HTTPException: 當 workspace 不存在時
    """
    # 檢查 workspace 是否存在
    current_user_id = _require_current_user_id(request)
    try:
        workspace = service.get(workspace_id, current_user_id=current_user_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
            )

        if not service.mark_workspace_rebuilding(
            workspace_id,
            current_user_id=current_user_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=request.state.translate("workspace.restart_failed")
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc

    # 加入背景任務
    background_tasks.add_task(run_restart_workspace_task, workspace_id)

    return {
        "message": request.state.translate("workspace.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.post(
    "/{workspace_id}/restart-browser",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重啟 Browser 容器",
    responses=build_responses(400, 404, 500),
)
def restart_browser(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """重啟工作區的 Browser 容器

    此操作會在背景執行以下步驟：
    1. 重啟 Browser Docker container
    2. 更新 browser_status 狀態

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID

    Raises:
        HTTPException: 當 workspace 不存在或沒有 Browser 容器時
    """
    # 檢查 workspace 是否存在
    current_user_id = _require_current_user_id(request)
    try:
        workspace = service.get(workspace_id, current_user_id=current_user_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
            )

        if (
            workspace.provisioner != "kubernetes"
            and not workspace.runtime_status.browser_container_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=request.state.translate("workspace.browser.not_found")
            )

        if not service.mark_browser_restarting(
            workspace_id,
            current_user_id=current_user_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=request.state.translate("workspace.browser.restart_failed")
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc

    # 加入背景任務
    background_tasks.add_task(run_restart_browser_task, workspace_id)

    return {
        "message": request.state.translate("workspace.browser.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.post(
    "/{workspace_id}/restart-nextjs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重啟 Next.js 容器",
    responses=build_responses(400, 404, 500),
)
def restart_nextjs(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """重啟工作區的 Next.js 容器

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID
    """
    current_user_id = _require_current_user_id(request)
    try:
        workspace = service.get(workspace_id, current_user_id=current_user_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
            )

        if (
            workspace.provisioner != "kubernetes"
            and not workspace.runtime_status.nextjs_container_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=request.state.translate("workspace.nextjs.not_found"),
            )

        if not service.mark_nextjs_restarting(
            workspace_id,
            current_user_id=current_user_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=request.state.translate("workspace.nextjs.restart_failed"),
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc

    background_tasks.add_task(run_restart_nextjs_task, workspace_id)

    return {
        "message": request.state.translate("workspace.nextjs.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.get(
    "/{workspace_id}/shares",
    response_model=WorkspaceShareListResponse,
    summary="列出工作區分享名單",
    responses=_build_workspace_share_responses(401, 403, 404, 500),
)
def list_workspace_shares(
    workspace_id: str,
    request: Request,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShareListResponse:
    current_user_id = _require_current_user_id(request)
    try:
        return service.list_shares(workspace_id, current_user_id=current_user_id)
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(str(exc), request.state.translate),
        ) from exc


@router.post(
    "/{workspace_id}/shares",
    response_model=WorkspaceShare,
    status_code=status.HTTP_201_CREATED,
    summary="新增工作區分享",
    responses=_build_workspace_share_responses(400, 401, 403, 404, 409, 500),
)
def create_workspace_share(
    workspace_id: str,
    payload: WorkspaceShareCreateRequest,
    request: Request,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShare:
    current_user_id = _require_current_user_id(request)
    try:
        return service.create_share(
            workspace_id,
            payload,
            current_user_id=current_user_id,
        )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail in {WORKSPACE_NOT_FOUND_MESSAGE, WORKSPACE_SHARE_TARGET_NOT_FOUND_MESSAGE}
            else status.HTTP_409_CONFLICT
            if detail == WORKSPACE_SHARE_CONFLICT_MESSAGE
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=_workspace_share_error_detail(detail, request.state.translate)) from exc


@router.patch(
    "/{workspace_id}/shares/{share_id}",
    response_model=WorkspaceShare,
    summary="更新工作區分享角色",
    responses=_build_workspace_share_responses(400, 401, 403, 404, 500),
)
def update_workspace_share(
    workspace_id: str,
    share_id: str,
    payload: WorkspaceShareUpdateRequest,
    request: Request,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShare:
    current_user_id = _require_current_user_id(request)
    try:
        result = service.update_share(
            workspace_id,
            share_id,
            payload,
            current_user_id=current_user_id,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_workspace_share_error_detail(WORKSPACE_SHARE_NOT_FOUND_MESSAGE, request.state.translate),
            )
        return result
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(str(exc), request.state.translate),
        ) from exc


@router.delete(
    "/{workspace_id}/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移除工作區分享",
    responses=_build_workspace_share_responses(401, 403, 404, 500),
)
def delete_workspace_share(
    workspace_id: str,
    share_id: str,
    request: Request,
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    current_user_id = _require_current_user_id(request)
    try:
        deleted = service.delete_share(
            workspace_id,
            share_id,
            current_user_id=current_user_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_workspace_share_error_detail(WORKSPACE_SHARE_NOT_FOUND_MESSAGE, request.state.translate),
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(str(exc), request.state.translate),
        ) from exc


@router.get(
    "/{workspace_id}/knowledge-bases",
    response_model=WorkspaceKnowledgeBaseAttachmentListResponse,
    summary="列出工作區掛載的 knowledge bases",
    responses=_build_workspace_kb_responses(401, 403, 404, 500),
)
def list_workspace_knowledge_bases(
    workspace_id: str,
    request: Request,
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> WorkspaceKnowledgeBaseAttachmentListResponse:
    current_user_id = _require_current_user_id(request)
    try:
        attachments = service.list_attachments_for_workspace(
            user_id=current_user_id,
            workspace_id=workspace_id,
        )
        return WorkspaceKnowledgeBaseAttachmentListResponse(
            items=[
                WorkspaceKnowledgeBaseAttachment(
                    id=attachment.id,
                    kb_id=attachment.knowledge_base.id,
                    name=attachment.knowledge_base.name,
                    slug=attachment.knowledge_base.slug,
                    role=None,
                    mount_alias=attachment.mount_alias,
                    mode=attachment.mode,
                    attached_by_id=attachment.attached_by_id,
                    created_at=attachment.created_at,
                    updated_at=attachment.updated_at,
                )
                for attachment in attachments
            ]
        )
    except (WorkspaceAccessDeniedError, KnowledgeBaseAccessDeniedError, PermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="KB_ACCESS_DENIED",
                message=_translate_workspace_kb_message(request.state.translate, str(exc)),
            ),
        ) from exc
    except (ValueError, KnowledgeBaseNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_kb_not_found_detail(str(exc), request.state.translate),
        ) from exc


@router.post(
    "/{workspace_id}/knowledge-bases",
    response_model=WorkspaceKnowledgeBaseAttachment,
    status_code=status.HTTP_201_CREATED,
    summary="掛載 knowledge base 到工作區",
    responses=_build_workspace_kb_responses(400, 401, 403, 404, 409, 500),
)
def create_workspace_knowledge_base_attachment(
    workspace_id: str,
    payload: WorkspaceKnowledgeBaseAttachmentCreateRequest,
    request: Request,
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> WorkspaceKnowledgeBaseAttachment:
    current_user_id = _require_current_user_id(request)
    try:
        attachment = service.attach(
            user_id=current_user_id,
            workspace_id=workspace_id,
            kb_id=payload.kb_id,
            mount_alias=payload.mount_alias,
            mode=payload.mode,
        )
        return WorkspaceKnowledgeBaseAttachment(
            id=attachment.id,
            kb_id=attachment.knowledge_base.id,
            name=attachment.knowledge_base.name,
            slug=attachment.knowledge_base.slug,
            role=None,
            mount_alias=attachment.mount_alias,
            mode=attachment.mode,
            attached_by_id=attachment.attached_by_id,
            created_at=attachment.created_at,
            updated_at=attachment.updated_at,
        )
    except (WorkspaceAccessDeniedError, KnowledgeBaseAccessDeniedError, PermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="KB_ACCESS_DENIED",
                message=_translate_workspace_kb_message(request.state.translate, str(exc)),
            ),
        ) from exc
    except KnowledgeBaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_workspace_kb_conflict_detail(str(exc), request.state.translate),
        ) from exc
    except (ValueError, KnowledgeBaseNotFoundError) as exc:
        message = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if message in {WORKSPACE_NOT_FOUND_MESSAGE, KB_NOT_FOUND_MESSAGE, KB_ATTACHMENT_NOT_FOUND_MESSAGE}
            else status.HTTP_400_BAD_REQUEST
        )
        detail = (
            _workspace_kb_not_found_detail(message, request.state.translate)
            if status_code == status.HTTP_404_NOT_FOUND
            else _build_workspace_kb_error_detail(
                code="KB_INVALID_REQUEST",
                message=_translate_workspace_kb_message(request.state.translate, message),
            )
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.patch(
    "/{workspace_id}/knowledge-bases/{attachment_id}",
    response_model=WorkspaceKnowledgeBaseAttachment,
    summary="更新工作區 knowledge base 掛載",
    responses=_build_workspace_kb_responses(400, 401, 403, 404, 409, 500),
)
def update_workspace_knowledge_base_attachment(
    workspace_id: str,
    attachment_id: str,
    payload: WorkspaceKnowledgeBaseAttachmentUpdateRequest,
    request: Request,
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> WorkspaceKnowledgeBaseAttachment:
    current_user_id = _require_current_user_id(request)
    try:
        attachment = service.update_attachment(
            user_id=current_user_id,
            attachment_id=attachment_id,
            mount_alias=payload.mount_alias,
            mode=payload.mode,
        )
        return WorkspaceKnowledgeBaseAttachment(
            id=attachment.id,
            kb_id=attachment.knowledge_base.id,
            name=attachment.knowledge_base.name,
            slug=attachment.knowledge_base.slug,
            role=None,
            mount_alias=attachment.mount_alias,
            mode=attachment.mode,
            attached_by_id=attachment.attached_by_id,
            created_at=attachment.created_at,
            updated_at=attachment.updated_at,
        )
    except (WorkspaceAccessDeniedError, KnowledgeBaseAccessDeniedError, PermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="KB_ACCESS_DENIED",
                message=_translate_workspace_kb_message(request.state.translate, str(exc)),
            ),
        ) from exc
    except KnowledgeBaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_workspace_kb_conflict_detail(str(exc), request.state.translate),
        ) from exc
    except (ValueError, KnowledgeBaseNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_kb_not_found_detail(str(exc), request.state.translate),
        ) from exc


@router.delete(
    "/{workspace_id}/knowledge-bases/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移除工作區 knowledge base 掛載",
    responses=_build_workspace_kb_responses(401, 403, 404, 500),
)
def delete_workspace_knowledge_base_attachment(
    workspace_id: str,
    attachment_id: str,
    request: Request,
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> None:
    current_user_id = _require_current_user_id(request)
    try:
        service.detach(user_id=current_user_id, attachment_id=attachment_id)
    except (WorkspaceAccessDeniedError, KnowledgeBaseAccessDeniedError, PermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="KB_ACCESS_DENIED",
                message=_translate_workspace_kb_message(request.state.translate, str(exc)),
            ),
        ) from exc
    except (ValueError, KnowledgeBaseNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_kb_not_found_detail(str(exc), request.state.translate),
        ) from exc


__all__ = ["router"]
