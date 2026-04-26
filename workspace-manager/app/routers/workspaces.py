"""Workspace API"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from app.core.openapi import build_responses
from app.db import models as db_models
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
    WorkspaceAccessDeniedError,
    WorkspaceError,
    WorkspaceNotFoundError,
)
from app.db.database import SessionLocal
from app.services.workspace_lifecycle_service import (
    run_delete_workspace_task,
    run_restart_workspace_task,
    run_restart_browser_task,
    run_restart_canvas_task,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_WORKSPACE_KB_ERROR_DESCRIPTIONS = {
    400: "Workspace knowledge base request is invalid, e.g., malformed payload. `detail.message` will be localized based on request language.",
    403: "Current user does not have permission to operate on workspace or knowledge base attachments. `detail.message` will be localized based on request language.",
    404: "Specified workspace, knowledge base, or attachment does not exist. `detail.message` will be localized based on request language.",
    409: "Workspace knowledge base state conflict, e.g., duplicate attachment or mount alias conflict. `detail.message` will be localized based on request language.",
}

_WORKSPACE_SHARE_ERROR_DESCRIPTIONS = {
    400: "Workspace share request is invalid, e.g., cannot share to owner. `detail.message` will be localized based on request language.",
    403: "Current user does not have permission to manage workspace shares. `detail.message` will be localized based on request language.",
    404: "Specified workspace, share target, or workspace share does not exist. `detail.message` will be localized based on request language.",
    409: "Workspace share state conflict, e.g., duplicate share to same user. `detail.message` will be localized based on request language.",
}

_WORKSPACE_SHARE_ERROR_EXAMPLES = {
    400: {
        "shareOwnerForbidden": {
            "summary": "Cannot share workspace with owner",
            "value": {
                "detail": {
                    "code": "WORKSPACE_INVALID_SHARE_TARGET",
                    "message": "Cannot share a workspace with its owner",
                    "details": {"resource": "workspace_share"},
                }
            },
        }
    },
    404: {
        "shareNotFound": {
            "summary": "Specified workspace share does not exist",
            "value": {
                "detail": {
                    "code": "WORKSPACE_SHARE_NOT_FOUND",
                    "message": "Workspace share not found",
                    "details": {"resource": "workspace_share"},
                }
            },
        }
    },
    409: {
        "shareConflict": {
            "summary": "Duplicate share to same user",
            "value": {
                "detail": {
                    "code": "WORKSPACE_SHARE_CONFLICT",
                    "message": "Workspace share already exists",
                    "details": {"resource": "workspace_share"},
                }
            },
        }
    },
}

_WORKSPACE_KB_ERROR_EXAMPLES = {
    404: {
        "attachmentNotFound": {
            "summary": "Specified knowledge base attachment does not exist",
            "value": {
                "detail": {
                    "code": "KB_ATTACHMENT_NOT_FOUND",
                    "message": "Knowledge base attachment not found",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        }
    },
    409: {
        "duplicateAttachment": {
            "summary": "Duplicate attachment of same knowledge base",
            "value": {
                "detail": {
                    "code": "KB_ALREADY_ATTACHED",
                    "message": "Knowledge base is already attached to this workspace",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "aliasConflict": {
            "summary": "Mount alias conflict",
            "value": {
                "detail": {
                    "code": "KB_MOUNT_ALIAS_CONFLICT",
                    "message": "Knowledge base mount alias already exists",
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


def _translate_workspace_share_message(translate, code: str) -> str:
    mapping = {
        "WORKSPACE_NOT_FOUND": translate("workspace.not_found"),
        "WORKSPACE_SHARE_TARGET_NOT_FOUND": translate("workspace.share.target_not_found"),
        "WORKSPACE_INVALID_SHARE_TARGET": translate("workspace.share.owner_forbidden"),
        "WORKSPACE_SHARE_CONFLICT": translate("workspace.share.conflict"),
        "WORKSPACE_SHARE_NOT_FOUND": translate("workspace.share.not_found"),
    }
    return mapping.get(code, translate("knowledge_base.invalid.request"))


def _workspace_share_error_detail(code: str, translate) -> dict:
    mapping = {
        "WORKSPACE_NOT_FOUND": "workspace",
        "WORKSPACE_SHARE_TARGET_NOT_FOUND": "user",
        "WORKSPACE_INVALID_SHARE_TARGET": "workspace_share",
        "WORKSPACE_SHARE_CONFLICT": "workspace_share",
        "WORKSPACE_SHARE_NOT_FOUND": "workspace_share",
    }
    return _build_workspace_kb_error_detail(
        code=code,
        message=_translate_workspace_share_message(translate, code),
        details={"resource": mapping.get(code, "workspace_share")},
    )


def _translate_workspace_kb_message(translate, code: str) -> str:
    mapping = {
        "WORKSPACE_NOT_FOUND": translate("workspace.not_found"),
        "KB_NOT_FOUND": translate("knowledge_base.not_found"),
        "KB_ATTACHMENT_NOT_FOUND": translate("knowledge_base.attachment_not_found"),
        "KB_ALREADY_ATTACHED": translate("knowledge_base.already_attached"),
        "KB_MOUNT_ALIAS_CONFLICT": translate("knowledge_base.alias_conflict"),
        "KB_ACCESS_DENIED": translate("knowledge_base.access_denied"),
        "KB_PERMISSION_DENIED": translate("knowledge_base.permission_denied"),
    }
    return mapping.get(code, translate("knowledge_base.invalid.request"))


def _translate_workspace_value_error(translate, code: str, params: dict | None = None) -> str:
    params = params or {}
    if code == "WORKSPACE_OWNER_NOT_FOUND":
        return translate("workspace.owner_not_found")
    if code == "WORKSPACE_FIREWALL_UNAVAILABLE":
        return translate("workspace.firewall_unavailable")
    if code == "WORKSPACE_RUNTIME_RESOURCES_UNSUPPORTED":
        return translate("workspace.runtime_resources_unsupported")
    if code == "WORKSPACE_PORT_MAPPINGS_UNSUPPORTED":
        return translate("workspace.port_mappings_unsupported")
    if code == "WORKSPACE_INVALID_NAMESPACE":
        return translate("workspace.invalid_namespace", namespace=params.get("namespace", ""))
    return translate("knowledge_base.invalid.request")


def _workspace_kb_not_found_detail(code: str, translate) -> dict:
    mapping = {
        "WORKSPACE_NOT_FOUND": "workspace",
        "KB_NOT_FOUND": "knowledge_base",
        "KB_ATTACHMENT_NOT_FOUND": "knowledge_base_attachment",
    }
    return _build_workspace_kb_error_detail(
        code=code,
        message=_translate_workspace_kb_message(translate, code),
        details={"resource": mapping.get(code, "knowledge_base")},
    )


def _workspace_kb_conflict_detail(code: str, translate) -> dict:
    mapping = {
        "KB_ALREADY_ATTACHED": "knowledge_base_attachment",
        "KB_MOUNT_ALIAS_CONFLICT": "knowledge_base_attachment",
    }
    return _build_workspace_kb_error_detail(
        code=code,
        message=_translate_workspace_kb_message(translate, code),
        details={"resource": mapping.get(code, "knowledge_base_attachment")},
    )

_RUNTIME_LOG_STAGE_KEYS = {
    "queued": "workspace.runtime_log.queued",
    "provisioning": "workspace.runtime_log.provisioning",
    "preparing": "workspace.runtime_log.preparing",
    "provisioned": "workspace.runtime_log.provisioned",
    "browser_starting": "workspace.runtime_log.browser_starting",
    "browser_ready": "workspace.runtime_log.browser_ready",
    "canvas_starting": "workspace.runtime_log.canvas_starting",
    "canvas_ready": "workspace.runtime_log.canvas_ready",
    "completed": "workspace.runtime_log.completed",
    "browser_restarting": "workspace.runtime_log.browser_restarting",
    "browser_running": "workspace.runtime_log.browser_running",
    "canvas_restarting": "workspace.runtime_log.canvas_restarting",
    "canvas_running": "workspace.runtime_log.canvas_running",
}

_RUNTIME_LOG_EXACT_KEYS = {
    "No Browser container associated": "workspace.runtime_log.browser_not_found",
    "No Browser container found for this workspace": "workspace.runtime_log.browser_not_found",
    "No Canvas container associated": "workspace.runtime_log.canvas_not_found",
    "No Canvas container found for this workspace": "workspace.runtime_log.canvas_not_found",
}

_RUNTIME_LOG_PREFIX_KEYS = (
    ("Browser ContainerStartFailed: ", "workspace.runtime_log.browser_error"),
    ("Browser container startup failed: ", "workspace.runtime_log.browser_error"),
    ("Canvas ContainerStartFailed: ", "workspace.runtime_log.canvas_error"),
    ("Canvas container startup failed: ", "workspace.runtime_log.canvas_error"),
    ("Rebuild failed: ", "workspace.runtime_log.rebuild_error"),
    ("Rebuild failed: ", "workspace.runtime_log.rebuild_error"),
    ("Removed directory: ", "workspace.runtime_log.volume_removed"),
    ("Removed directory: ", "workspace.runtime_log.volume_removed"),
    ("Failed to remove directory: ", "workspace.runtime_log.volume_error"),
    ("Failed to remove directory: ", "workspace.runtime_log.volume_error"),
)

_RUNTIME_LOG_GENERIC_KEY = "workspace.runtime_log.generic"


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
            return translate(key)

    stage_key = _RUNTIME_LOG_STAGE_KEYS.get(stage)
    if stage_key:
        return translate(stage_key)

    return translate(_RUNTIME_LOG_GENERIC_KEY)


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


def _should_schedule_kb_runtime_sync(workspace: object) -> bool:
    provisioner = getattr(workspace, "provisioner", None)
    runtime_container_id = getattr(workspace, "runtime_container_id", None)
    return provisioner == "docker" and isinstance(runtime_container_id, str) and bool(runtime_container_id)


@router.get(
    "/",
    response_model=WorkspaceListResponse,
    summary="List workspaces",
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
    summary="Create workspace",
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
    except WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_workspace_value_error(
                request.state.translate,
                getattr(exc, "code", "WORKSPACE_INVALID_REQUEST"),
                getattr(exc, "params", {}),
            ),
        ) from exc


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
    summary="Get workspace details",
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
    summary="Get runtime deployment logs",
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

    # Manually convert database object to Pydantic model
    result = []
    for log in logs:
        log_entry = WorkspaceRuntimeLogEntry(
            id=log.id,
            workspace_id=log.workspace_id,
            stage=log.stage,
            message=_translate_runtime_log_message(log.stage, log.message, request.state.translate),
            metadata=log.log_metadata,  # Map log_metadata to metadata
            created_at=log.created_at,
        )
        result.append(log_entry)

    return result


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
    summary="UpdateWorkspace",
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
        # Only firewall configuration changes need additional sync to workspace-runtime, other columns are persisted by manager itself.
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

        # Docker workspace firewall is applied through runtime internal API.
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
    except WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_workspace_value_error(
                request.state.translate,
                getattr(exc, "code", "WORKSPACE_INVALID_REQUEST"),
                getattr(exc, "params", {}),
            ),
        ) from exc


async def _sync_firewall_to_runtime(workspace_id: str, firewall_config: dict):
    """Background task: Sync firewall settings to workspace-runtime"""
    logger.info(f"Starting background firewall settings sync - workspace_id: {workspace_id}")

    db = SessionLocal()
    try:
        sync_service = RuntimeSyncService(db)
        result = await sync_service.sync_firewall_to_runtime(workspace_id, firewall_config)

        if result.get("success"):
            logger.info(f"Firewall settings sync succeeded - workspace_id: {workspace_id}")
        else:
            logger.warning(f"Firewall settings sync skipped - workspace_id: {workspace_id}, reason: {result.get('message')}")

    except Exception as e:
        logger.error(f"Firewall settings sync failed - workspace_id: {workspace_id}, error: {e}", exc_info=True)
    finally:
        db.close()


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete workspace",
    responses=build_responses(404, 500),
)
def delete_workspace(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """Delete workspace

    This operation executes the following steps in background:
    1. Stop and delete Docker container
    2. Delete mounted data directory
    3. Delete workspace record from database

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI background task
        service: Workspace service

    Returns:
        dict: Contains message and workspace ID

    Raises:
        HTTPException: When workspace does not exist
    """
    # Check if workspace exists
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

    # Add to background task
    background_tasks.add_task(run_delete_workspace_task, workspace_id)

    return {
        "message": request.state.translate("workspace.deletion_started"),
        "workspaceId": workspace_id,
        "status": "deleting"
    }


@router.post(
    "/{workspace_id}/rebuild",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rebuild workspace runtime",
    responses=build_responses(404, 500),
)
def rebuild_workspace(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """Restart workspace container

    This operation executes the following steps in background:
    1. Restart Docker container
    2. Update workspace status

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI background task
        service: Workspace service

    Returns:
        dict: Contains message and workspace ID

    Raises:
        HTTPException: When workspace does not exist
    """
    # Check if workspace exists
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

    # Add to background task
    background_tasks.add_task(run_restart_workspace_task, workspace_id)

    return {
        "message": request.state.translate("workspace.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.post(
    "/{workspace_id}/restart-browser",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Restart browser container",
    responses=build_responses(400, 404, 500),
)
def restart_browser(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """Restart workspace browser container

    This operation executes the following steps in background:
    1. Restart browser Docker container
    2. Update browser_status status

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI background task
        service: Workspace service

    Returns:
        dict: Contains message and workspace ID

    Raises:
        HTTPException: When workspace does not exist or has no browser container
    """
    # Check if workspace exists
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

    # Add to background task
    background_tasks.add_task(run_restart_browser_task, workspace_id)

    return {
        "message": request.state.translate("workspace.browser.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.post(
    "/{workspace_id}/restart-canvas",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Restart canvas container",
    responses=build_responses(400, 404, 500),
)
def restart_canvas(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """Restart workspace canvas container

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI background task
        service: Workspace service

    Returns:
        dict: Contains message and workspace ID
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
            and not workspace.runtime_status.canvas_container_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=request.state.translate("workspace.canvas.not_found"),
            )

        if not service.mark_canvas_restarting(
            workspace_id,
            current_user_id=current_user_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=request.state.translate("workspace.canvas.restart_failed"),
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc

    background_tasks.add_task(run_restart_canvas_task, workspace_id)

    return {
        "message": request.state.translate("workspace.canvas.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.get(
    "/{workspace_id}/shares",
    response_model=WorkspaceShareListResponse,
    summary="List workspace shares",
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
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(getattr(exc, "code", "WORKSPACE_NOT_FOUND"), request.state.translate),
        ) from exc


@router.post(
    "/{workspace_id}/shares",
    response_model=WorkspaceShare,
    status_code=status.HTTP_201_CREATED,
    summary="Add workspace share",
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
    except WorkspaceError as exc:
        code = getattr(exc, "code", "WORKSPACE_INVALID_REQUEST")
        status_code = (
            status.HTTP_404_NOT_FOUND
            if code in {"WORKSPACE_NOT_FOUND", "WORKSPACE_SHARE_TARGET_NOT_FOUND"}
            else status.HTTP_409_CONFLICT
            if code == "WORKSPACE_SHARE_CONFLICT"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code,
            detail=_workspace_share_error_detail(code, request.state.translate),
        ) from exc


@router.patch(
    "/{workspace_id}/shares/{share_id}",
    response_model=WorkspaceShare,
    summary="Update workspace share role",
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
                detail=_workspace_share_error_detail("WORKSPACE_SHARE_NOT_FOUND", request.state.translate),
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
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(getattr(exc, "code", "WORKSPACE_NOT_FOUND"), request.state.translate),
        ) from exc


@router.delete(
    "/{workspace_id}/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace share",
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
                detail=_workspace_share_error_detail("WORKSPACE_SHARE_NOT_FOUND", request.state.translate),
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(getattr(exc, "code", "WORKSPACE_NOT_FOUND"), request.state.translate),
        ) from exc


@router.get(
    "/{workspace_id}/knowledge-bases",
    response_model=WorkspaceKnowledgeBaseAttachmentListResponse,
    summary="List workspace knowledge bases",
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
        code = getattr(exc, "code", "KB_ACCESS_DENIED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code=code,
                message=_translate_workspace_kb_message(request.state.translate, code),
            ),
        ) from exc
    except (WorkspaceNotFoundError, KnowledgeBaseNotFoundError) as exc:
        code = getattr(exc, "code", "KB_NOT_FOUND")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_kb_not_found_detail(code, request.state.translate),
        ) from exc


@router.post(
    "/{workspace_id}/knowledge-bases",
    response_model=WorkspaceKnowledgeBaseAttachment,
    status_code=status.HTTP_201_CREATED,
    summary="Attach knowledge base to workspace",
    responses=_build_workspace_kb_responses(400, 401, 403, 404, 409, 500),
)
def create_workspace_knowledge_base_attachment(
    workspace_id: str,
    payload: WorkspaceKnowledgeBaseAttachmentCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
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
        workspace = service.db.get(db_models.Workspace, workspace_id)
        if workspace is not None and _should_schedule_kb_runtime_sync(workspace):
            background_tasks.add_task(run_runtime_provision_task, workspace_id)
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
        code = getattr(exc, "code", "KB_ACCESS_DENIED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code=code,
                message=_translate_workspace_kb_message(request.state.translate, code),
            ),
        ) from exc
    except KnowledgeBaseConflictError as exc:
        code = getattr(exc, "code", "KB_CONFLICT")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_workspace_kb_conflict_detail(code, request.state.translate),
        ) from exc
    except (WorkspaceError, KnowledgeBaseNotFoundError) as exc:
        code = getattr(exc, "code", "KB_INVALID_REQUEST")
        status_code = (
            status.HTTP_404_NOT_FOUND
            if code in {"WORKSPACE_NOT_FOUND", "KB_NOT_FOUND", "KB_ATTACHMENT_NOT_FOUND"}
            else status.HTTP_400_BAD_REQUEST
        )
        detail = (
            _workspace_kb_not_found_detail(code, request.state.translate)
            if status_code == status.HTTP_404_NOT_FOUND
            else _build_workspace_kb_error_detail(
                code=code,
                message=_translate_workspace_value_error(
                    request.state.translate,
                    code,
                    getattr(exc, "params", {}),
                ) if code.startswith("WORKSPACE_") else _translate_workspace_kb_message(request.state.translate, code),
            )
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.patch(
    "/{workspace_id}/knowledge-bases/{attachment_id}",
    response_model=WorkspaceKnowledgeBaseAttachment,
    summary="Update workspace knowledge base attachment",
    responses=_build_workspace_kb_responses(400, 401, 403, 404, 409, 500),
)
def update_workspace_knowledge_base_attachment(
    workspace_id: str,
    attachment_id: str,
    payload: WorkspaceKnowledgeBaseAttachmentUpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
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
        workspace = service.db.get(db_models.Workspace, workspace_id)
        if workspace is not None and _should_schedule_kb_runtime_sync(workspace):
            background_tasks.add_task(run_runtime_provision_task, workspace_id)
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
        code = getattr(exc, "code", "KB_ACCESS_DENIED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code=code,
                message=_translate_workspace_kb_message(request.state.translate, code),
            ),
        ) from exc
    except KnowledgeBaseConflictError as exc:
        code = getattr(exc, "code", "KB_CONFLICT")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_workspace_kb_conflict_detail(code, request.state.translate),
        ) from exc
    except (WorkspaceNotFoundError, KnowledgeBaseNotFoundError) as exc:
        code = getattr(exc, "code", "KB_NOT_FOUND")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_kb_not_found_detail(code, request.state.translate),
        ) from exc


@router.delete(
    "/{workspace_id}/knowledge-bases/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace knowledge base attachment",
    responses=_build_workspace_kb_responses(401, 403, 404, 500),
)
def delete_workspace_knowledge_base_attachment(
    workspace_id: str,
    attachment_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> None:
    current_user_id = _require_current_user_id(request)
    try:
        service.detach(user_id=current_user_id, attachment_id=attachment_id)
        workspace = service.db.get(db_models.Workspace, workspace_id)
        if workspace is not None and _should_schedule_kb_runtime_sync(workspace):
            background_tasks.add_task(run_runtime_provision_task, workspace_id)
    except (WorkspaceAccessDeniedError, KnowledgeBaseAccessDeniedError, PermissionError) as exc:
        code = getattr(exc, "code", "KB_ACCESS_DENIED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_kb_error_detail(
                code=code,
                message=_translate_workspace_kb_message(request.state.translate, code),
            ),
        ) from exc
    except (WorkspaceNotFoundError, KnowledgeBaseNotFoundError) as exc:
        code = getattr(exc, "code", "KB_NOT_FOUND")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_kb_not_found_detail(code, request.state.translate),
        ) from exc


__all__ = ["router"]
