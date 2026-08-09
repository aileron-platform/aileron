"""Workspace API"""

from __future__ import annotations

import logging
from typing import Literal, Optional
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.api_error import ApiErrorResponse, authorization_error_detail
from app.core.openapi import build_responses
from app.db import models as db_models
from app.db.database import SessionLocal
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.knowledge_base.access import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
)
from app.modules.knowledge_base.attachments import (
    AttachmentMutationProjection,
    KnowledgeBaseAttachmentService,
)
from app.modules.knowledge_base.dependencies import (
    get_knowledge_base_attachment_service,
    get_knowledge_base_mount_reconcile_service,
)
from app.modules.knowledge_base.errors import KnowledgeBaseError
from app.modules.knowledge_base.mount_reconcile import (
    KnowledgeBaseMountReconcileService,
)
from app.modules.workspace.availability import (
    WorkspaceAvailabilityError,
    WorkspaceAvailabilityService,
)
from app.modules.workspace.availability_models import (
    WorkspaceAvailabilityActionResponse,
    WorkspaceAvailabilityResponse,
)
from app.modules.workspace.browser_credential_access import (
    WorkspaceBrowserCredentialError,
    WorkspaceBrowserCredentialService,
)
from app.modules.workspace.browser_credential_models import (
    BrowserAccessResponse,
    BrowserCredentialRotationResponse,
)
from app.modules.workspace.capabilities import WorkspaceCapabilities
from app.modules.workspace.catalog import (
    WorkspaceAccessDeniedError,
    WorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceService,
)
from app.modules.workspace.dependencies import (
    get_runtime_provision_service,
    get_workspace_availability_service,
    get_workspace_browser_credential_service,
    get_workspace_firewall_service,
    get_workspace_lifecycle_service,
    get_workspace_runtime_access_service,
    get_workspace_service,
)
from app.modules.workspace.firewall import (
    WorkspaceFirewallRetryNotAllowedError,
    WorkspaceFirewallRevisionConflictError,
    WorkspaceFirewallService,
    WorkspaceFirewallUnavailableError,
)
from app.modules.workspace.firewall_contract import (
    FirewallReplacementRequest,
    FirewallResource,
)
from app.modules.workspace.lifecycle import (
    WorkspaceLifecycleCommandResult,
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleService,
)
from app.modules.workspace.models import (
    BrowserExtensionPairingAssertionResponse,
    KnowledgeBaseMountSync,
    KnowledgeBaseMountSyncResponse,
    WorkspaceCreateRequest,
    WorkspaceDeleteRequest,
    WorkspaceKnowledgeBaseAttachment,
    WorkspaceKnowledgeBaseAttachmentCreateRequest,
    WorkspaceKnowledgeBaseAttachmentListResponse,
    WorkspaceKnowledgeBaseAttachmentMutationResponse,
    WorkspaceKnowledgeBaseAttachmentUpdateRequest,
    WorkspaceKnowledgeBaseErrorResponse,
    WorkspaceListResponse,
    WorkspaceReadDetail,
    WorkspaceRuntimeLogEntry,
    WorkspaceSensitiveSettings,
    WorkspaceSensitiveSettingsReplaceRequest,
    WorkspaceShare,
    WorkspaceShareCandidate,
    WorkspaceShareCandidateListResponse,
    WorkspaceShareCreateRequest,
    WorkspaceShareListResponse,
    WorkspaceShareUpdateRequest,
    WorkspaceUpdateRequest,
)
from app.modules.workspace.runtime.access import (
    WorkspaceRuntimeAccessError,
    WorkspaceRuntimeAccessService,
)
from app.modules.workspace.runtime.assertions import (
    BrowserExtensionPairingAssertionContext,
    ExecutionGrantContext,
    RuntimeAssertionConfigurationError,
    RuntimeAssertionContextError,
    RuntimeAssertionService,
)
from app.modules.workspace.runtime.provisioning import RuntimeProvisionService
from app.modules.workspace.runtime.job_repository import (
    WORKSPACE_DELETE_PHASE_QUEUED,
)
from app.modules.workspace.runtime.sync import RuntimeSyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class ExecutionGrantRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    runtime_instance_id: str = Field(alias="runtimeInstanceId")
    audience: Literal["workspace-runtime", "workspace-terminal"]
    actions: tuple[str, ...]


class ExecutionGrantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    grant: str
    expires_in: Literal[60] = Field(default=60, alias="expiresIn")


@router.get(
    "/gateway/authorize",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def authorize_workspace_gateway(
    request: Request,
    workspace_id: str = Header(alias="X-Aileron-Workspace-Id"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> Response:
    try:
        AuthorizationOperationPolicy(service.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_DETAIL_READ,
        )
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/{workspace_id}/browser/access",
    response_model=BrowserAccessResponse,
    status_code=status.HTTP_200_OK,
    responses=build_responses(401, 403, 404, 409, 500, 503),
)
def access_workspace_browser(
    workspace_id: str,
    request: Request,
    response: Response,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceBrowserCredentialService = Depends(
        get_workspace_browser_credential_service
    ),
) -> BrowserAccessResponse:
    try:
        result = service.access(
            actor=actor,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
    except WorkspaceBrowserCredentialError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=_workspace_browser_error_detail(request, exc),
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return result


@router.post(
    "/{workspace_id}/browser/credentials/rotate",
    response_model=BrowserCredentialRotationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=build_responses(401, 403, 404, 500),
)
def rotate_workspace_browser_credentials(
    workspace_id: str,
    request: Request,
    response: Response,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceBrowserCredentialService = Depends(
        get_workspace_browser_credential_service
    ),
) -> BrowserCredentialRotationResponse:
    try:
        result = service.rotate(
            actor=actor,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
    except WorkspaceBrowserCredentialError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=_workspace_browser_error_detail(request, exc),
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return result


def _workspace_browser_error_detail(
    request: Request,
    exc: WorkspaceBrowserCredentialError,
) -> dict[str, object]:
    if exc.http_status == status.HTTP_401_UNAUTHORIZED:
        message = request.state.translate("auth.unauthenticated")
    elif exc.http_status == status.HTTP_404_NOT_FOUND:
        message = request.state.translate("workspace.not_found")
    elif exc.http_status == status.HTTP_403_FORBIDDEN:
        message = request.state.translate("workspace.access_denied")
    elif exc.code == "BROWSER_CONNECTIVITY_NOT_READY":
        message = request.state.translate("workspace.browser_connectivity_not_ready")
    elif exc.code == "BROWSER_CONNECTIVITY_UNAVAILABLE":
        message = request.state.translate("workspace.browser_connectivity_unavailable")
    else:
        return {"errorCode": exc.code}
    return authorization_error_detail(exc.code, message)


_WORKSPACE_KB_ERROR_DESCRIPTIONS = {
    400: "Workspace knowledge base request is invalid.",
    403: "Current user cannot manage workspace knowledge base attachments.",
    404: "Specified workspace, knowledge base, or attachment does not exist.",
    409: "Workspace knowledge base mount state conflicts with the request.",
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
                    "errorCode": "WORKSPACE_INVALID_SHARE_TARGET",
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
                    "errorCode": "WORKSPACE_SHARE_NOT_FOUND",
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
                    "errorCode": "WORKSPACE_SHARE_CONFLICT",
                    "message": "Workspace share already exists",
                    "details": {"resource": "workspace_share"},
                }
            },
        }
    },
}


def _serializable_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    errors = exc.errors(include_input=False)
    for error in errors:
        ctx = error.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            ctx["error"] = str(ctx["error"])
    return errors


def _workspace_request_validation_error(
    exc: ValidationError,
    *,
    translate,
) -> HTTPException:
    if any(error["type"] == "extra_forbidden" for error in exc.errors()):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": "WORKSPACE_INVALID_REQUEST"},
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "message": translate("workspace.invalid_request"),
            "errors": _serializable_validation_errors(exc),
        },
    )


_WORKSPACE_KB_ERROR_EXAMPLES = {
    404: {
        "attachmentNotFound": {
            "summary": "Specified knowledge base attachment does not exist",
            "value": {
                "detail": {
                    "errorCode": "KB_ATTACHMENT_NOT_FOUND",
                    "correlationId": "52b41ab6-3768-49ea-8ca7-d19b97dd67d9",
                }
            },
        }
    },
    409: {
        "duplicateAttachment": {
            "summary": "Duplicate attachment of same knowledge base",
            "value": {
                "detail": {
                    "errorCode": "KB_ALREADY_ATTACHED",
                    "correlationId": "52b41ab6-3768-49ea-8ca7-d19b97dd67d9",
                }
            },
        },
        "aliasConflict": {
            "summary": "Mount alias conflict",
            "value": {
                "detail": {
                    "errorCode": "KB_MOUNT_ALIAS_CONFLICT",
                    "correlationId": "52b41ab6-3768-49ea-8ca7-d19b97dd67d9",
                }
            },
        },
    },
}


def _build_workspace_kb_responses(*status_codes: int) -> dict[int, dict]:
    return build_responses(
        *status_codes,
        model=WorkspaceKnowledgeBaseErrorResponse,
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
        model=ApiErrorResponse,
        descriptions=_WORKSPACE_SHARE_ERROR_DESCRIPTIONS,
        examples={
            status_code: _WORKSPACE_SHARE_ERROR_EXAMPLES[status_code]
            for status_code in status_codes
            if status_code in _WORKSPACE_SHARE_ERROR_EXAMPLES
        },
    )


def _build_workspace_error_detail(
    *, code: str, message: str, details: dict | None = None
) -> dict:
    # JSON envelope key is `errorCode` (consistent with KB/marketplace/workspace-runtime).
    return {
        "errorCode": code,
        "message": message,
        "details": details or {},
    }


def _translate_workspace_share_message(translate, code: str) -> str:
    mapping = {
        "WORKSPACE_NOT_FOUND": translate("workspace.not_found"),
        "WORKSPACE_SHARE_TARGET_NOT_FOUND": translate(
            "workspace.share.target_not_found"
        ),
        "WORKSPACE_SHARE_TARGET_NOT_AUTHORIZABLE": translate(
            "workspace.share.target_not_authorizable"
        ),
        "WORKSPACE_INVALID_SHARE_TARGET": translate("workspace.share.owner_forbidden"),
        "WORKSPACE_SHARE_CONFLICT": translate("workspace.share.conflict"),
        "WORKSPACE_SHARE_NOT_FOUND": translate("workspace.share.not_found"),
    }
    return mapping.get(code, translate("workspace.invalid_request"))


def _workspace_share_error_detail(code: str, translate) -> dict:
    mapping = {
        "WORKSPACE_NOT_FOUND": "workspace",
        "WORKSPACE_SHARE_TARGET_NOT_FOUND": "user",
        "WORKSPACE_SHARE_TARGET_NOT_AUTHORIZABLE": "user",
        "WORKSPACE_INVALID_SHARE_TARGET": "workspace_share",
        "WORKSPACE_SHARE_CONFLICT": "workspace_share",
        "WORKSPACE_SHARE_NOT_FOUND": "workspace_share",
    }
    return _build_workspace_error_detail(
        code=code,
        message=_translate_workspace_share_message(translate, code),
        details={"resource": mapping.get(code, "workspace_share")},
    )


def _translate_workspace_value_error(translate, code: str) -> str:
    if code == "WORKSPACE_OWNER_NOT_FOUND":
        return translate("workspace.owner_not_found")
    if code == "WORKSPACE_FIREWALL_UNAVAILABLE":
        return translate("workspace.firewall_unavailable")
    return translate("workspace.invalid_request")


def _workspace_mount_error_detail(
    request: Request,
    *,
    code: str,
    details: dict | None = None,
) -> dict:
    if code in {
        "WORKSPACE_NOT_FOUND",
        "WORKSPACE_ACCESS_DENIED",
    }:
        message = request.state.translate("workspace.not_found")
    elif code in {
        "WORKSPACE_OPERATION_DENIED",
        "WORKSPACE_RUNTIME_ACTION_FORBIDDEN",
    }:
        message = request.state.translate("workspace.access_denied")
    elif code == "RESOURCE_DELETE_CONFIRMATION_MISMATCH":
        message = request.state.translate("workspace.delete_confirmation_mismatch")
    elif code == "WORKSPACE_DELETE_CONFLICT":
        message = request.state.translate("workspace.delete_active_state")
    else:
        message = request.state.translate("workspace.invalid_request")
    error_details = {
        "correlationId": request.state.correlation_id,
        **(details or {}),
    }
    return authorization_error_detail(
        code,
        message,
        details=error_details,
    )


def _knowledge_base_mount_sync(
    workspace: db_models.Workspace,
) -> KnowledgeBaseMountSync:
    status_value = (
        workspace.knowledge_base_mount_sync_status
        if workspace.knowledge_base_mount_sync_status in {"ready", "degraded"}
        else "syncing"
    )
    return KnowledgeBaseMountSync(
        status=status_value,
        desired_revision=workspace.knowledge_base_mount_desired_revision,
        observed_revision=workspace.knowledge_base_mount_observed_revision,
        last_known_good_revision=workspace.knowledge_base_mount_active_revision,
        error_code=workspace.knowledge_base_mount_error_code,
        compensating=(workspace.knowledge_base_mount_sync_status == "compensating"),
    )


def _workspace_attachment_item(
    attachment: (
        db_models.WorkspaceKnowledgeBaseAttachment | AttachmentMutationProjection
    ),
) -> WorkspaceKnowledgeBaseAttachment:
    if isinstance(attachment, AttachmentMutationProjection):
        name = attachment.name
        slug = attachment.slug
        status_value = attachment.status
        created_at = None
        updated_at = None
    else:
        name = attachment.knowledge_base.name
        slug = attachment.knowledge_base.slug
        status_value = "active"
        created_at = attachment.created_at
        updated_at = attachment.updated_at
    return WorkspaceKnowledgeBaseAttachment(
        id=attachment.id,
        kb_id=attachment.kb_id,
        name=name,
        slug=slug,
        mount_alias=attachment.mount_alias,
        status=status_value,
        attached_by_id=attachment.attached_by_id,
        created_at=created_at,
        updated_at=updated_at,
    )


def _raise_workspace_mount_error(request: Request, exc: Exception) -> None:
    code = getattr(
        exc,
        "error_code",
        getattr(exc, "code", "KB_INVALID_REQUEST"),
    )
    details = getattr(exc, "params", {})
    if isinstance(exc, AuthorizationOperationError):
        status_code = exc.http_status
    elif isinstance(
        exc,
        (WorkspaceAccessDeniedError, KnowledgeBaseAccessDeniedError, PermissionError),
    ):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(
        exc,
        (WorkspaceNotFoundError, KnowledgeBaseNotFoundError),
    ):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, KnowledgeBaseConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, (WorkspaceError, KnowledgeBaseError)):
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        raise exc
    raise HTTPException(
        status_code=status_code,
        detail=_workspace_mount_error_detail(
            request,
            code=code,
            details=details,
        ),
    ) from exc


def _workspace_lifecycle_response(
    result: WorkspaceLifecycleCommandResult,
) -> dict[str, object]:
    response: dict[str, object] = {
        "workspaceId": result.workspace_id,
        "status": result.runtime_status,
        "jobId": result.job.id,
        "correlationId": result.job.correlation_id,
        "rootCorrelationId": result.job.root_correlation_id,
    }
    if result.job.operation == "workspace_delete":
        response["phase"] = (
            result.job.job_metadata.get("phase")
            if isinstance(result.job.job_metadata.get("phase"), str)
            else WORKSPACE_DELETE_PHASE_QUEUED
        )
    if result.component is not None:
        response["component"] = result.component
    if result.target_revision is not None:
        response["targetRevision"] = result.target_revision
    return response


def _raise_workspace_lifecycle_error(request: Request, exc: Exception) -> None:
    if isinstance(exc, WorkspaceLifecycleConflictError):
        status_code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if exc.code == "RESOURCE_DELETE_CONFIRMATION_MISMATCH"
            else status.HTTP_409_CONFLICT
        )
    elif isinstance(exc, WorkspaceAccessDeniedError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, WorkspaceNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    else:
        raise exc
    raise HTTPException(
        status_code=status_code,
        detail=_workspace_mount_error_detail(
            request,
            code=getattr(exc, "code", "WORKSPACE_LIFECYCLE_FAILED"),
        ),
    ) from exc


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


def _require_authorization_operation(
    request: Request,
    db: Session,
    actor: AuthorizationActor,
    operation: OperationId,
    *,
    workspace_id: str | None = None,
) -> None:
    try:
        policy = AuthorizationOperationPolicy(db)
        if workspace_id is None:
            policy.require_platform_operation(actor, operation)
        else:
            policy.require_workspace_operation(actor, workspace_id, operation)
    except AuthorizationOperationError as exc:
        message = (
            request.state.translate("workspace.not_found")
            if exc.http_status == status.HTTP_404_NOT_FOUND
            else request.state.translate("workspace.access_denied")
        )
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(exc.error_code, message),
        ) from exc


@router.get(
    "/{workspace_id}/availability",
    response_model=WorkspaceAvailabilityResponse,
    summary="Get Manager control-plane Workspace availability",
    responses=build_responses(401, 403, 404, 500),
)
def get_workspace_availability(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceAvailabilityService = Depends(get_workspace_availability_service),
) -> WorkspaceAvailabilityResponse:
    try:
        return service.get(
            actor=actor,
            workspace_id=workspace_id,
        )
    except WorkspaceAvailabilityError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=_workspace_mount_error_detail(request, code=exc.code),
        ) from exc


@router.post(
    "/{workspace_id}/availability/actions/{action}",
    response_model=WorkspaceAvailabilityActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request an allowed Workspace recovery action",
    responses=build_responses(401, 403, 404, 409, 422, 500),
)
def request_workspace_availability_action(
    workspace_id: str,
    action: Literal["start", "retry", "rebuild"],
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceAvailabilityService = Depends(get_workspace_availability_service),
) -> WorkspaceAvailabilityActionResponse:
    try:
        return service.request_action(
            actor=actor,
            workspace_id=workspace_id,
            action=action,
            correlation_id=request.state.correlation_id,
        )
    except WorkspaceAvailabilityError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=_workspace_mount_error_detail(request, code=exc.code),
        ) from exc
    except Exception as exc:
        _raise_workspace_lifecycle_error(request, exc)


@router.post(
    "/{workspace_id}/execution-grants",
    response_model=ExecutionGrantResponse,
    summary="Issue an audience-bound Workspace Execution Access Grant",
    responses=_build_workspace_kb_responses(
        401,
        403,
        404,
        409,
        422,
        423,
        500,
        503,
    ),
)
def create_workspace_execution_grant(
    workspace_id: str,
    request: Request,
    payload: ExecutionGrantRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceRuntimeAccessService = Depends(
        get_workspace_runtime_access_service
    ),
) -> ExecutionGrantResponse:
    try:
        if not payload.actions:
            raise WorkspaceRuntimeAccessError("WORKSPACE_RUNTIME_ACTION_INVALID", 422)
        access = None
        for action in payload.actions:
            access = service.authorize(
                actor=actor,
                workspace_id=workspace_id,
                action=action,
                runtime_instance_id=payload.runtime_instance_id,
            )
        if access is None:
            raise WorkspaceRuntimeAccessError("WORKSPACE_RUNTIME_ACTION_INVALID", 422)
        grant = RuntimeAssertionService.from_settings().sign_execution_grant(
            ExecutionGrantContext(
                actor_user_id=access.actor.user_id,
                workspace_id=access.workspace.id,
                runtime_instance_id=payload.runtime_instance_id,
                runtime_access_revision=access.workspace.runtime_access_revision,
                audience=payload.audience,
                actions=payload.actions,
            )
        )
        return ExecutionGrantResponse(grant=grant)
    except WorkspaceRuntimeAccessError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=_workspace_mount_error_detail(request, code=exc.code),
        ) from exc
    except (RuntimeAssertionConfigurationError, RuntimeAssertionContextError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_workspace_mount_error_detail(
                request,
                code="WORKSPACE_EXECUTION_GRANT_INVALID",
            ),
        ) from exc


@router.post(
    "/{workspace_id}/browser-extension-pairing-assertions",
    response_model=BrowserExtensionPairingAssertionResponse,
    status_code=status.HTTP_200_OK,
    summary="Issue a one-time assertion for the current browser generation",
    responses=_build_workspace_kb_responses(401, 403, 404, 423, 500),
)
def create_browser_extension_pairing_assertion(
    workspace_id: str,
    request: Request,
    response: Response,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    access_service: WorkspaceRuntimeAccessService = Depends(
        get_workspace_runtime_access_service
    ),
) -> BrowserExtensionPairingAssertionResponse:
    try:
        access = access_service.authorize_current_browser_automation(
            actor=actor,
            workspace_id=workspace_id,
        )
        runtime_instance_id = access.workspace.runtime_instance_id
        browser_workload_identity = access.workspace.browser_container_id
        if runtime_instance_id is None or browser_workload_identity is None:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_BROWSER_WORKLOAD_NOT_READY",
                423,
            )
        assertion = (
            RuntimeAssertionService.from_settings().sign_browser_extension_pairing(
                BrowserExtensionPairingAssertionContext(
                    actor_user_id=access.actor.user_id,
                    workspace_id=access.workspace.id,
                    runtime_instance_id=runtime_instance_id,
                    browser_workload_identity=browser_workload_identity,
                    pairing_session_id=str(uuid4()),
                )
            )
        )
    except WorkspaceRuntimeAccessError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=_workspace_mount_error_detail(request, code=exc.code),
        ) from exc
    except (RuntimeAssertionConfigurationError, RuntimeAssertionContextError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_workspace_mount_error_detail(
                request,
                code="WORKSPACE_BROWSER_PAIRING_ASSERTION_UNAVAILABLE",
            ),
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return BrowserExtensionPairingAssertionResponse(
        assertion=assertion,
        runtimeInstanceId=runtime_instance_id,
    )


@router.post(
    "/{workspace_id}/knowledge-base-mount-sync/retry",
    response_model=KnowledgeBaseMountSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry the current failed knowledge base mount revision",
    responses=_build_workspace_kb_responses(401, 403, 404, 409, 500),
)
def retry_workspace_knowledge_base_mount_sync(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseMountReconcileService = Depends(
        get_knowledge_base_mount_reconcile_service
    ),
) -> KnowledgeBaseMountSyncResponse:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_ATTACHMENT_WRITE,
        workspace_id=workspace_id,
    )
    try:
        workspace, _ = service.retry_failed_mount(
            actor=actor,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        return KnowledgeBaseMountSyncResponse(
            knowledge_base_mount_sync=_knowledge_base_mount_sync(workspace)
        )
    except Exception as exc:
        _raise_workspace_mount_error(request, exc)


@router.get(
    "",
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
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceListResponse:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_COLLECTION_READ,
    )
    return service.list(
        page=page,
        page_size=page_size,
        current_user_id=actor.user_id,
        status=status,
        search=search,
    )


@router.post(
    "",
    response_model=WorkspaceReadDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace",
    responses=build_responses(400, 401, 422, 500),
)
async def create_workspace(
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceReadDetail:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_CREATE,
    )
    try:
        payload_data = await request.json()
        payload = WorkspaceCreateRequest.model_validate(payload_data)
        payload.owner_id = actor.user_id

        return service.create(
            payload,
            correlation_id=request.state.correlation_id,
        )
    except ValidationError as exc:
        raise _workspace_request_validation_error(
            exc,
            translate=request.state.translate,
        ) from exc
    except WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_workspace_value_error(
                request.state.translate,
                getattr(exc, "code", "WORKSPACE_INVALID_REQUEST"),
            ),
        ) from exc


@router.get(
    "/{workspace_id}/sensitive-settings",
    response_model=WorkspaceSensitiveSettings,
    summary="Get masked Workspace sensitive settings",
    responses=build_responses(401, 403, 404, 500),
)
def get_workspace_sensitive_settings(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceSensitiveSettings:
    try:
        settings = service.get_sensitive_settings(
            workspace_id,
            actor=actor,
        )
        if settings is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=authorization_error_detail(
                    "WORKSPACE_ACCESS_DENIED",
                    request.state.translate("workspace.not_found"),
                ),
            )
        return settings
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("workspace.access_denied"),
            ),
        ) from exc


@router.put(
    "/{workspace_id}/sensitive-settings",
    response_model=WorkspaceSensitiveSettings,
    summary="Replace Workspace sensitive settings",
    responses=build_responses(401, 403, 404, 422, 500),
)
def replace_workspace_sensitive_settings(
    workspace_id: str,
    payload: WorkspaceSensitiveSettingsReplaceRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceSensitiveSettings:
    try:
        settings = service.replace_sensitive_settings(
            workspace_id,
            payload,
            actor=actor,
        )
        if settings is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=authorization_error_detail(
                    "WORKSPACE_ACCESS_DENIED",
                    request.state.translate("workspace.not_found"),
                ),
            )
        return settings
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("workspace.access_denied"),
            ),
        ) from exc


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceReadDetail,
    summary="Get workspace details",
    responses=build_responses(404, 500),
)
def get_workspace(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceReadDetail:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_DETAIL_READ,
        workspace_id=workspace_id,
    )
    try:
        workspace = service.get(
            workspace_id,
            actor=actor,
        )
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found"),
            )
        return workspace
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc


@router.get(
    "/{workspace_id}/firewall",
    response_model=FirewallResource,
    summary="Get Workspace firewall desired state",
    responses=build_responses(401, 403, 404, 500),
)
def get_workspace_firewall(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceFirewallService = Depends(get_workspace_firewall_service),
) -> FirewallResource:
    try:
        return service.get(
            workspace_id=workspace_id,
            actor=actor,
        )
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.code},
        ) from exc
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errorCode": exc.code},
        ) from exc
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("workspace.access_denied"),
            ),
        ) from exc


@router.put(
    "/{workspace_id}/firewall",
    response_model=FirewallResource,
    summary="Replace Workspace firewall desired state",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
def replace_workspace_firewall(
    workspace_id: str,
    payload: FirewallReplacementRequest,
    request: Request,
    response: Response,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceFirewallService = Depends(get_workspace_firewall_service),
) -> FirewallResource:
    try:
        result = service.replace(
            workspace_id=workspace_id,
            actor=actor,
            payload=payload,
        )
        response.status_code = (
            status.HTTP_202_ACCEPTED if result.changed else status.HTTP_200_OK
        )
        return result.resource
    except WorkspaceFirewallRevisionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"errorCode": exc.code},
        ) from exc
    except WorkspaceFirewallUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": exc.code},
        ) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.code},
        ) from exc
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errorCode": exc.code},
        ) from exc
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("workspace.access_denied"),
            ),
        ) from exc


@router.post(
    "/{workspace_id}/firewall/retry",
    response_model=FirewallResource,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry the failed Workspace firewall desired state",
    responses=build_responses(400, 401, 403, 404, 409, 500),
)
def retry_workspace_firewall(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceFirewallService = Depends(get_workspace_firewall_service),
) -> FirewallResource:
    try:
        return service.retry(
            workspace_id=workspace_id,
            actor=actor,
        )
    except WorkspaceFirewallRetryNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"errorCode": exc.code},
        ) from exc
    except WorkspaceFirewallUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errorCode": exc.code},
        ) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errorCode": exc.code},
        ) from exc
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errorCode": exc.code},
        ) from exc
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("workspace.access_denied"),
            ),
        ) from exc


@router.get(
    "/{workspace_id}/capabilities",
    response_model=WorkspaceCapabilities,
    summary="Get workspace capabilities",
    responses=build_responses(403, 404, 500),
)
def get_workspace_capabilities(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceCapabilities:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        workspace_id=workspace_id,
    )
    try:
        capabilities = service.get_capabilities(
            workspace_id,
            actor=actor,
        )
        if not capabilities:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found"),
            )
        return capabilities
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc


@router.put(
    "/{workspace_id}/capabilities",
    response_model=WorkspaceCapabilities,
    summary="Update workspace capabilities",
    responses=build_responses(403, 404, 422, 500),
)
def update_workspace_capabilities(
    workspace_id: str,
    payload: WorkspaceCapabilities,
    request: Request,
    background_tasks: BackgroundTasks,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceCapabilities:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        workspace_id=workspace_id,
    )
    try:
        capabilities = service.update_capabilities(
            workspace_id,
            payload,
            actor=actor,
        )
        if not capabilities:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found"),
            )
        workspace_record = service.db.get(db_models.Workspace, workspace_id)
        runtime_url = (
            workspace_record.runtime_internal_url if workspace_record else None
        )
        if (
            workspace_record
            and workspace_record.runtime_status == "running"
            and runtime_url
        ):
            background_tasks.add_task(
                _sync_capabilities_to_runtime,
                workspace_id,
                runtime_url,
                capabilities.model_dump(),
            )
        return capabilities
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        ) from exc


async def _sync_capabilities_to_runtime(
    workspace_id: str,
    runtime_url: str,
    capabilities: dict,
) -> None:
    """Background task: Sync workspace capabilities to workspace-runtime."""
    logger.info(f"Starting background capabilities sync - workspace_id: {workspace_id}")

    db = SessionLocal()
    try:
        sync_service = RuntimeSyncService(db)
        result = await sync_service.sync_capabilities_to_runtime_url(
            workspace_id,
            runtime_url,
            capabilities,
        )
        if result.get("success"):
            logger.info(f"Capabilities sync succeeded - workspace_id: {workspace_id}")
        else:
            logger.warning(
                f"Capabilities sync skipped - workspace_id: {workspace_id}, reason: {result.get('message')}"
            )
    except Exception as e:
        logger.error(
            f"Capabilities sync failed - workspace_id: {workspace_id}, error: {e}",
            exc_info=True,
        )
    finally:
        db.close()


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
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: RuntimeProvisionService = Depends(get_runtime_provision_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceRuntimeLogEntry]:
    _require_authorization_operation(
        request,
        workspace_service.db,
        actor,
        OperationId.WORKSPACE_DETAIL_READ,
        workspace_id=workspace_id,
    )
    try:
        workspace = workspace_service.get(
            workspace_id,
            actor=actor,
        )
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found"),
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
            message=_translate_runtime_log_message(
                log.stage, log.message, request.state.translate
            ),
            metadata=log.log_metadata,  # Map log_metadata to metadata
            created_at=log.created_at,
        )
        result.append(log_entry)

    return result


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceReadDetail,
    summary="UpdateWorkspace",
    responses=build_responses(404, 422, 500),
)
async def update_workspace(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceReadDetail:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_METADATA_WRITE,
        workspace_id=workspace_id,
    )
    try:
        payload_data = await request.json()
        payload = WorkspaceUpdateRequest.model_validate(payload_data)
    except ValidationError as exc:
        raise _workspace_request_validation_error(
            exc,
            translate=request.state.translate,
        ) from exc
    try:
        workspace = service.update(
            workspace_id,
            payload,
            actor=actor,
            correlation_id=request.state.correlation_id,
        )
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found"),
            )

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
            ),
        ) from exc


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete workspace",
    responses=build_responses(403, 404, 409, 422, 500),
)
def delete_workspace(
    workspace_id: str,
    payload: WorkspaceDeleteRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceLifecycleService = Depends(get_workspace_lifecycle_service),
) -> dict[str, object]:
    try:
        return _workspace_lifecycle_response(
            service.request_delete(
                actor=actor,
                workspace_id=workspace_id,
                confirmation_name=payload.confirmation_name,
                correlation_id=request.state.correlation_id,
            )
        )
    except Exception as exc:
        _raise_workspace_lifecycle_error(request, exc)


@router.post(
    "/{workspace_id}/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start workspace runtime",
    responses=build_responses(403, 404, 409, 500),
)
def start_workspace(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceLifecycleService = Depends(get_workspace_lifecycle_service),
) -> dict[str, object]:
    try:
        return _workspace_lifecycle_response(
            service.request_start(
                actor=actor,
                workspace_id=workspace_id,
                correlation_id=request.state.correlation_id,
            )
        )
    except Exception as exc:
        _raise_workspace_lifecycle_error(request, exc)


@router.post(
    "/{workspace_id}/stop",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stop workspace runtime",
    responses=build_responses(403, 404, 409, 500),
)
def stop_workspace(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceLifecycleService = Depends(get_workspace_lifecycle_service),
) -> dict[str, object]:
    try:
        return _workspace_lifecycle_response(
            service.request_stop(
                actor=actor,
                workspace_id=workspace_id,
                correlation_id=request.state.correlation_id,
            )
        )
    except Exception as exc:
        _raise_workspace_lifecycle_error(request, exc)


@router.post(
    "/{workspace_id}/components/{component}/restart",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Restart one workspace component",
    responses=build_responses(400, 403, 404, 409, 500),
)
def restart_workspace_component(
    workspace_id: str,
    component: Literal["runtime", "browser", "canvas"],
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceLifecycleService = Depends(get_workspace_lifecycle_service),
) -> dict[str, object]:
    try:
        return _workspace_lifecycle_response(
            service.request_component_restart(
                actor=actor,
                workspace_id=workspace_id,
                component=component,
                correlation_id=request.state.correlation_id,
            )
        )
    except Exception as exc:
        _raise_workspace_lifecycle_error(request, exc)


@router.get(
    "/{workspace_id}/share-candidate-users",
    response_model=WorkspaceShareCandidateListResponse,
    summary="Search shareable workspace users",
    responses=_build_workspace_share_responses(401, 403, 404, 500),
)
def list_workspace_share_candidate_users(
    workspace_id: str,
    request: Request,
    query: str = Query(default=""),
    limit: int = Query(default=8, ge=1, le=50),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShareCandidateListResponse:
    try:
        items = service.list_share_candidate_users(
            actor=actor,
            workspace_id=workspace_id,
            query=query,
            limit=limit,
        )
        return WorkspaceShareCandidateListResponse(
            items=[
                WorkspaceShareCandidate(id=item_id, label=label)
                for item_id, label in items
            ]
        )
    except Exception as exc:
        _raise_workspace_mount_error(request, exc)


@router.get(
    "/{workspace_id}/share-candidate-groups",
    response_model=WorkspaceShareCandidateListResponse,
    summary="Search shareable workspace groups",
    responses=_build_workspace_share_responses(401, 403, 404, 500),
)
def list_workspace_share_candidate_groups(
    workspace_id: str,
    request: Request,
    query: str = Query(default=""),
    limit: int = Query(default=8, ge=1, le=50),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShareCandidateListResponse:
    try:
        items = service.list_share_candidate_groups(
            actor=actor,
            workspace_id=workspace_id,
            query=query,
            limit=limit,
        )
        return WorkspaceShareCandidateListResponse(
            items=[
                WorkspaceShareCandidate(id=item_id, label=label)
                for item_id, label in items
            ]
        )
    except Exception as exc:
        _raise_workspace_mount_error(request, exc)


@router.get(
    "/{workspace_id}/shares",
    response_model=WorkspaceShareListResponse,
    summary="List workspace shares",
    responses=_build_workspace_share_responses(401, 403, 404, 500),
)
def list_workspace_shares(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShareListResponse:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_ACCESS_MANAGE,
        workspace_id=workspace_id,
    )
    try:
        return service.list_shares(
            workspace_id,
            actor=actor,
        )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(
                getattr(exc, "code", "WORKSPACE_NOT_FOUND"), request.state.translate
            ),
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
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShare:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_ACCESS_MANAGE,
        workspace_id=workspace_id,
    )
    try:
        return service.create_share(
            workspace_id,
            payload,
            actor=actor,
            correlation_id=request.state.correlation_id,
            root_correlation_id=getattr(
                request.state,
                "root_correlation_id",
                request.state.correlation_id,
            ),
        )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except WorkspaceError as exc:
        code = getattr(exc, "code", "WORKSPACE_INVALID_REQUEST")
        status_code = (
            status.HTTP_404_NOT_FOUND
            if code in {"WORKSPACE_NOT_FOUND", "WORKSPACE_SHARE_TARGET_NOT_FOUND"}
            else (
                status.HTTP_409_CONFLICT
                if code == "WORKSPACE_SHARE_CONFLICT"
                else status.HTTP_400_BAD_REQUEST
            )
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
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceShare:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_ACCESS_MANAGE,
        workspace_id=workspace_id,
    )
    try:
        result = service.update_share(
            workspace_id,
            share_id,
            payload,
            actor=actor,
            correlation_id=request.state.correlation_id,
            root_correlation_id=request.state.correlation_id,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_workspace_share_error_detail(
                    "WORKSPACE_SHARE_NOT_FOUND", request.state.translate
                ),
            )
        return result
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(
                getattr(exc, "code", "WORKSPACE_NOT_FOUND"), request.state.translate
            ),
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
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    _require_authorization_operation(
        request,
        service.db,
        actor,
        OperationId.WORKSPACE_ACCESS_MANAGE,
        workspace_id=workspace_id,
    )
    try:
        deleted = service.delete_share(
            workspace_id,
            share_id,
            actor=actor,
            correlation_id=request.state.correlation_id,
            root_correlation_id=request.state.correlation_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_workspace_share_error_detail(
                    "WORKSPACE_SHARE_NOT_FOUND", request.state.translate
                ),
            )
    except WorkspaceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_workspace_error_detail(
                code="WORKSPACE_ACCESS_DENIED",
                message=request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_workspace_share_error_detail(
                getattr(exc, "code", "WORKSPACE_NOT_FOUND"), request.state.translate
            ),
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
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseAttachmentService = Depends(
        get_knowledge_base_attachment_service
    ),
) -> WorkspaceKnowledgeBaseAttachmentListResponse:
    try:
        attachments = service.list_attachments_for_workspace(
            actor=actor,
            workspace_id=workspace_id,
        )
        workspace = service.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise KnowledgeBaseNotFoundError(
                "Workspace does not exist",
                code="WORKSPACE_NOT_FOUND",
            )
        return WorkspaceKnowledgeBaseAttachmentListResponse(
            items=[_workspace_attachment_item(item) for item in attachments],
            knowledge_base_mount_sync=_knowledge_base_mount_sync(workspace),
        )
    except Exception as exc:
        _raise_workspace_mount_error(request, exc)


@router.post(
    "/{workspace_id}/knowledge-bases",
    response_model=WorkspaceKnowledgeBaseAttachmentMutationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Attach knowledge base to workspace",
    responses=_build_workspace_kb_responses(400, 401, 403, 404, 409, 500),
)
def create_workspace_knowledge_base_attachment(
    workspace_id: str,
    payload: WorkspaceKnowledgeBaseAttachmentCreateRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseAttachmentService = Depends(
        get_knowledge_base_attachment_service
    ),
) -> WorkspaceKnowledgeBaseAttachmentMutationResponse:
    try:
        result = service.attach(
            actor=actor,
            workspace_id=workspace_id,
            kb_id=payload.kb_id,
            mount_alias=payload.mount_alias,
            correlation_id=request.state.correlation_id,
        )
        return WorkspaceKnowledgeBaseAttachmentMutationResponse(
            attachment=_workspace_attachment_item(result.attachment),
            knowledge_base_mount_sync=_knowledge_base_mount_sync(result.workspace),
        )
    except Exception as exc:
        _raise_workspace_mount_error(request, exc)


@router.patch(
    "/{workspace_id}/knowledge-bases/{attachment_id}",
    response_model=WorkspaceKnowledgeBaseAttachmentMutationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Update workspace knowledge base attachment",
    responses=_build_workspace_kb_responses(400, 401, 403, 404, 409, 500),
)
def update_workspace_knowledge_base_attachment(
    workspace_id: str,
    attachment_id: str,
    payload: WorkspaceKnowledgeBaseAttachmentUpdateRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseAttachmentService = Depends(
        get_knowledge_base_attachment_service
    ),
) -> WorkspaceKnowledgeBaseAttachmentMutationResponse:
    try:
        result = service.update_attachment(
            actor=actor,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            mount_alias=payload.mount_alias,
            correlation_id=request.state.correlation_id,
        )
        return WorkspaceKnowledgeBaseAttachmentMutationResponse(
            attachment=_workspace_attachment_item(result.attachment),
            knowledge_base_mount_sync=_knowledge_base_mount_sync(result.workspace),
        )
    except Exception as exc:
        _raise_workspace_mount_error(request, exc)


@router.delete(
    "/{workspace_id}/knowledge-bases/{attachment_id}",
    response_model=WorkspaceKnowledgeBaseAttachmentMutationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Remove workspace knowledge base attachment",
    responses=_build_workspace_kb_responses(401, 403, 404, 409, 500),
)
def delete_workspace_knowledge_base_attachment(
    workspace_id: str,
    attachment_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseAttachmentService = Depends(
        get_knowledge_base_attachment_service
    ),
) -> WorkspaceKnowledgeBaseAttachmentMutationResponse:
    try:
        result = service.detach(
            actor=actor,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            correlation_id=request.state.correlation_id,
        )
        return WorkspaceKnowledgeBaseAttachmentMutationResponse(
            attachment=_workspace_attachment_item(result.attachment),
            knowledge_base_mount_sync=_knowledge_base_mount_sync(result.workspace),
        )
    except Exception as exc:
        _raise_workspace_mount_error(request, exc)


__all__ = ["router"]
