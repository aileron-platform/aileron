"""Template Git version control and SSH keys management routes"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.models import (
    GitCloneRequest,
    GitCommitRequest,
    GitOperationResponse,
    GitRemoteUrlRequest,
    GitRepositoryInitRequest,
    GitRepositoryStatus,
    GitUserConfig,
    GitUserConfigResponse,
    SSHKeysUpdateRequest,
    TemplateBlobResponse,
    TemplateChangesResponse,
    TemplateCheckoutRequest,
    TemplateCheckoutResponse,
    TemplateCommitFilesResponse,
    TemplateCommitListResponse,
    TemplateCommitResponse,
    TemplateDiscardRequest,
    TemplateDiscardResponse,
    TemplateDiffResponse,
    TemplateRemoteRequest,
    TemplateRemoteResponse,
    TemplateStageRequest,
    TemplateStageResponse,
    TemplateUnstageRequest,
    TemplateUnstageResponse,
    TemplateVersionControlBranchListResponse,
    TemplateVersionControlStatus,
)
from app.services.template_git_service import TemplateGitService

logger = logging.getLogger(__name__)
router = APIRouter()


def _translate_git_result(translate, result) -> str:
    code = getattr(result, "code", "")
    params = getattr(result, "params", {}) or {}

    if code == "GIT_REPO_NOT_FOUND":
        return translate("templates.git.repo_not_found")
    if code == "GIT_NO_CHANGES":
        return translate("templates.git.no_changes_to_commit")
    if code == "GIT_REMOTE_URL_EMPTY":
        return translate("templates.git.remote_url_empty")
    if code == "GIT_CLONE_TARGET_NOT_EMPTY":
        return translate("templates.git.clone_target_not_empty")
    if code == "GIT_REPOSITORY_ALREADY_INITIALIZED":
        return translate("templates.git.repository_already_initialized")
    if code == "GIT_REPOSITORY_INITIALIZED":
        return translate("templates.git.repository_initialized")
    if code == "GIT_REPOSITORY_INIT_FAILED":
        return translate("templates.git.repository_init_failed")
    if code == "GIT_REPO_ACCESS_FAILED":
        return translate("templates.git.repo_access_failed")
    if code == "GIT_CLONE_TARGET_HAS_CHANGES":
        return translate("templates.git.clone_target_has_changes")
    if code == "GIT_PULL_HAS_UNCOMMITTED_CHANGES":
        return translate("templates.git.pull_has_uncommitted_changes")
    if code == "GIT_PLUGINS_DIR_MISSING":
        return translate("templates.git.plugins_dir_missing")
    if code == "GIT_NO_TEMPLATES_FOUND":
        return translate("templates.git.no_templates_found")
    if code == "GIT_PUSH_REMOTE_NOT_CONFIGURED":
        return translate("templates.git.push_remote_not_configured")
    if code == "GIT_BRANCH_NOT_FOUND":
        return translate("templates.git.branch_not_found", branch=params.get("branch", ""))
    if code == "GIT_REMOTE_URL_SET_FAILED":
        return translate("templates.git.remote_url_set_error_simple")
    if code == "GIT_COMMIT_FAILED":
        return translate("templates.git.commit_failed_simple")
    if code == "GIT_PUSH_FAILED_LOCAL_COMMITTED":
        return translate("templates.git.push_failed_local_committed_simple")
    if code == "GIT_COMMIT_PUSH_SUCCESS":
        return translate("templates.git.commit_push_success", commit_info=params.get("commitInfo", ""))
    if code == "GIT_COMMIT_LOCAL_SUCCESS":
        return translate("templates.git.commit_local_success", commit_info=params.get("commitInfo", ""))
    if code == "GIT_PULL_CONFLICT":
        return translate("templates.git.pull_conflict_simple")
    if code == "GIT_PULL_FAILED":
        return translate("templates.git.pull_failed_simple")
    if code == "GIT_PULL_SUCCESS":
        return translate("templates.git.pull_success")
    if code == "GIT_CLONE_REMOTE_MISMATCH":
        return translate("templates.git.clone_remote_mismatch", current_url=params.get("currentUrl", ""), new_url=params.get("newUrl", ""))
    if code == "GIT_CHECKOUT_BRANCH_FAILED":
        return translate("templates.git.checkout_branch_failed_simple", branch=params.get("branch", ""))
    if code == "GIT_CLONE_FAILED":
        return translate("templates.git.clone_failed_simple")
    if code == "GIT_CLONE_SUCCESS":
        return translate("templates.git.clone_success_detail", detail=params.get("detail", ""))
    if code == "GIT_CLONE_UPDATE_SUCCESS":
        return translate("templates.git.clone_update_success", detail=params.get("detail", ""))
    if code == "GIT_SCAN_FAILED":
        return translate("templates.git.scan_failed_simple")
    if code == "GIT_SCAN_SUCCESS":
        return translate("templates.git.scan_success", count=params.get("count", 0))
    if code == "GIT_USER_CONFIG_REQUIRED":
        return translate("templates.git_user_config_required")
    if code == "GIT_USER_CONFIG_UPDATE_FAILED":
        return translate("templates.git_user_config_update_failed")
    if code == "GIT_FETCH_SUCCESS":
        return translate("templates.git.fetch_success")
    if code == "GIT_PUSH_SUCCESS":
        return translate("templates.git.push_success")
    if code == "GIT_PATH_REQUIRED":
        return translate("templates.git.path_required")
    if code == "GIT_PATH_OUTSIDE_REPOSITORY":
        return translate("templates.git.path_outside_repository")
    return getattr(result, "message", "")


def _translate_git_exception(translate, exc: Exception) -> str:
    message = str(exc)
    if message in {
        "SSH_PRIVATE_KEY_INVALID",
        "SSH_PUBLIC_KEY_INVALID",
        "Private key format is incorrect",
        "Public key format is incorrect",
    }:
        return translate("templates.ssh_keys_invalid_format")
    if message == "SSH_KEY_GENERATION_FAILED":
        return translate("git.ssh_key_gen_failed_simple")
    if message in {
        "GIT_REPO_NOT_FOUND",
        "GIT_NO_CHANGES",
        "GIT_PATH_REQUIRED",
        "GIT_PATH_OUTSIDE_REPOSITORY",
        "GIT_REPOSITORY_ALREADY_INITIALIZED",
        "GIT_REPOSITORY_INIT_FAILED",
        "GIT_CLONE_TARGET_NOT_EMPTY",
    }:
        result = type("Result", (), {"code": message, "params": {}, "message": message})()
        return _translate_git_result(translate, result)
    return message


def get_template_git_service() -> TemplateGitService:
    """Get template git service instance"""
    return TemplateGitService()


# ============ Git version control API =============


@router.get(
    "/git/repository/status",
    response_model=GitRepositoryStatus,
    summary="Get Template Center Git repository initialization status",
    responses=build_responses(401, 500),
)
async def get_template_repository_status(
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> GitRepositoryStatus:
    return git_service.get_repository_status()


@router.post(
    "/git/repository/init",
    response_model=GitOperationResponse,
    summary="Initialize Template Center Git repository",
    responses=build_responses(401, 422, 500),
)
async def init_template_repository(
    request: Request,
    payload: GitRepositoryInitRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> GitOperationResponse:
    translate = request.state.translate
    try:
        result = git_service.init_repository(remote_url=payload.remote_url)
        if result.success:
            return GitOperationResponse(
                success=True,
                message=_translate_git_result(translate, result),
            )
        return GitOperationResponse(
            success=False,
            message=translate("templates.git.repository_init_failed"),
            error=_translate_git_result(translate, result),
            error_code=result.code,
        )
    except Exception as e:
        logger.error(f"Initialize Template Center Git repository failed: {e}")
        return GitOperationResponse(
            success=False,
            message=translate("templates.git.repository_init_failed"),
            error=_translate_git_exception(translate, e),
        )


@router.get(
    "/git/version-control/status",
    response_model=TemplateVersionControlStatus,
    summary="Get Template Center file-level Git status",
    responses=build_responses(401, 500),
)
async def get_template_version_control_status(
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateVersionControlStatus:
    return git_service.get_version_control_status()


@router.get(
    "/git/version-control/changes",
    response_model=TemplateChangesResponse,
    summary="Get Template Center file-level Git changes",
    responses=build_responses(401, 422, 500),
)
async def get_template_version_control_changes(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500, alias="pageSize"),
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateChangesResponse:
    return git_service.get_file_changes(page=page, page_size=page_size)


@router.get(
    "/git/version-control/branches",
    response_model=TemplateVersionControlBranchListResponse,
    summary="Get Template Center Git branch list",
    responses=build_responses(401, 500),
)
async def list_template_version_control_branches(
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateVersionControlBranchListResponse:
    return git_service.list_version_control_branches()


@router.post(
    "/git/version-control/branches/{branch_name:path}/checkout",
    response_model=TemplateCheckoutResponse,
    summary="Switch to or create Template Center Git branch",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def checkout_template_version_control_branch(
    branch_name: str,
    payload: TemplateCheckoutRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateCheckoutResponse:
    try:
        return git_service.checkout_branch(branch_name, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})


@router.post(
    "/git/version-control/stage",
    response_model=TemplateStageResponse,
    summary="Stage Template Center Git files",
    responses=build_responses(400, 401, 422, 500),
)
async def stage_template_version_control_changes(
    payload: TemplateStageRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateStageResponse:
    try:
        return git_service.stage(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})


@router.post(
    "/git/version-control/unstage",
    response_model=TemplateUnstageResponse,
    summary="Unstage Template Center Git files",
    responses=build_responses(400, 401, 422, 500),
)
async def unstage_template_version_control_changes(
    payload: TemplateUnstageRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateUnstageResponse:
    try:
        return git_service.unstage(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})


@router.post(
    "/git/version-control/discard",
    response_model=TemplateDiscardResponse,
    summary="Discard Template Center Git file changes",
    responses=build_responses(400, 401, 422, 500),
)
async def discard_template_version_control_changes(
    payload: TemplateDiscardRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateDiscardResponse:
    try:
        return git_service.discard(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})


@router.post(
    "/git/version-control/commit",
    response_model=TemplateCommitResponse,
    summary="Commit Template Center Git changes",
    responses=build_responses(400, 401, 422, 500),
)
async def commit_template_version_control_changes(
    payload: GitCommitRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateCommitResponse:
    try:
        return git_service.commit(message=payload.message, paths=payload.paths)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})


@router.get(
    "/git/version-control/commits",
    response_model=TemplateCommitListResponse,
    summary="List Template Center Git commit history",
    responses=build_responses(401, 422, 500),
)
async def list_template_version_control_commits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    branch: Optional[str] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateCommitListResponse:
    return git_service.list_commits(page=page, page_size=page_size, branch=branch)


@router.get(
    "/git/version-control/commits/{commit_id}/files",
    response_model=TemplateCommitFilesResponse,
    summary="Get Template Center Git commit files",
    responses=build_responses(401, 404, 500),
)
async def get_template_version_control_commit_files(
    commit_id: str,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateCommitFilesResponse:
    return git_service.get_commit_files(commit_id)


@router.get(
    "/git/version-control/diff",
    response_model=TemplateDiffResponse,
    summary="Get Template Center Git file diff",
    responses=build_responses(401, 422, 500),
)
async def get_template_version_control_diff(
    path: str = Query(...),
    head: str = Query("WORKTREE"),
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateDiffResponse:
    return git_service.diff(path=path, head=head)


@router.get(
    "/git/version-control/blob",
    response_model=TemplateBlobResponse,
    summary="Read Template Center Git file content",
    responses=build_responses(401, 422, 500),
)
async def get_template_version_control_blob(
    path: str = Query(...),
    revision: Optional[str] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateBlobResponse:
    return git_service.blob(path=path, revision=revision)


@router.post(
    "/git/version-control/fetch",
    response_model=TemplateRemoteResponse,
    summary="Fetch Template Center Git remote references",
    responses=build_responses(400, 401, 422, 500),
)
async def fetch_template_version_control(
    payload: TemplateRemoteRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateRemoteResponse:
    try:
        return git_service.fetch(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})


@router.post(
    "/git/version-control/pull",
    response_model=TemplateRemoteResponse,
    summary="Pull Template Center Git remote changes",
    responses=build_responses(400, 401, 422, 500),
)
async def pull_template_version_control(
    payload: TemplateRemoteRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateRemoteResponse:
    try:
        return git_service.pull(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})


@router.post(
    "/git/version-control/push",
    response_model=TemplateRemoteResponse,
    summary="Push Template Center Git changes",
    responses=build_responses(400, 401, 422, 500),
)
async def push_template_version_control(
    payload: TemplateRemoteRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> TemplateRemoteResponse:
    try:
        return git_service.push(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"errorCode": str(exc), "message": str(exc)})

@router.get(
    "/git/user-config",
    response_model=GitUserConfigResponse,
    summary="Get Git user information",
    responses=build_responses(401, 500),
)
async def get_git_user_config(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
) -> GitUserConfigResponse:
    """Get user information from git config --global settings"""

    try:
        config = git_service.get_user_config()
        return GitUserConfigResponse(success=True, data=config)
    except Exception as e:
        logger.error(f"Get Git user information failed: {e}")
        translate = request.state.translate
        return GitUserConfigResponse(
            success=False,
            error=translate("templates.git_user_config_get_failed")
        )


@router.post(
    "/git/user-config",
    response_model=GitOperationResponse,
    summary="Update Git user information",
    responses=build_responses(401, 422, 500),
)
async def update_git_user_config(
    request: Request,
    payload: GitUserConfig,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
) -> GitOperationResponse:
    """Update user information in git config --global"""

    try:
        translate = request.state.translate
        result = git_service.update_user_config(
            user_name=payload.user_name or "",
            user_email=payload.user_email or "",
        )

        if result.success:
            return GitOperationResponse(
                success=True,
                message=translate("templates.git_user_config_update_success")
            )
        return GitOperationResponse(
            success=False,
            message=translate("templates.git_user_config_update_failed"),
            error=_translate_git_result(translate, result),
            error_code=result.code,
        )
    except Exception as e:
        logger.error(f"Update Git user information failed: {e}")
        translate = request.state.translate
        return GitOperationResponse(
            success=False,
            message=translate("templates.git_user_config_update_failed"),
            error=_translate_git_exception(translate, e)
        )


@router.post(
    "/git/remote-url",
    response_model=GitOperationResponse,
    summary="Set Git remote repository URL",
    responses=build_responses(401, 422, 500),
)
async def set_git_remote_url(
    request: Request,
    payload: GitRemoteUrlRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
) -> GitOperationResponse:
    """Set or update Git remote repository URL (origin)"""

    try:
        translate = request.state.translate
        result = git_service.set_remote_url(url=payload.url)

        if result.success:
            return GitOperationResponse(
                success=True,
                message=translate("templates.git_remote_url_set_success")
            )
        return GitOperationResponse(
            success=False,
            message=translate("templates.git_remote_url_set_failed"),
            error=_translate_git_result(translate, result),
            error_code=result.code,
        )
    except Exception as e:
        logger.error(f"Set remote repository URL failed: {e}")
        translate = request.state.translate
        return GitOperationResponse(
            success=False,
            message=translate("templates.git_remote_url_set_failed"),
            error=_translate_git_exception(translate, e)
        )


def _rebuild_templates_background(
    task_id: str,
    git_service: TemplateGitService,
    db: Session,
    translate_func,
) -> None:
    """Background task: Rebuild template database"""
    from app.services.task_progress_service import get_task_progress_service, TaskStatus
    from app.services.template_service import TemplateService
    from sqlalchemy import text

    progress_service = get_task_progress_service()

    try:
        # Update status to executing
        progress_service.update_progress(
            task_id,
            progress=10,
            message=translate_func("templates.rebuild_clearing_data"),
            status=TaskStatus.RUNNING,
        )

        # Clear all old template data
        try:
            db.execute(text("DELETE FROM templates"))
            db.commit()
            logger.info("Cleared all old template data")
        except Exception as e:
            logger.error(f"Clear template data failed: {e}")
            progress_service.set_error(
                task_id,
                translate_func("templates.rebuild_clear_failed_simple")
            )
            return

        progress_service.update_progress(
            task_id,
            progress=30,
            message=translate_func("templates.rebuild_scanning")
        )

        # Scan and sync templates to database
        try:
            sync_result = git_service.scan_and_sync_templates()
            sync_success, sync_message, templates = sync_result

            if sync_success and templates:
                template_service = TemplateService(db)
                synced_count = 0
                total_templates = len(templates)

                for idx, template_info in enumerate(templates):
                    try:
                        # Calculate progress (30-95%)
                        progress = 30 + int((idx / total_templates) * 65)
                        progress_service.update_progress(
                            task_id,
                            progress=progress,
                            message=translate_func(
                                "templates.rebuild_scanning_template",
                                current=idx + 1,
                                total=total_templates,
                                template_id=template_info['id']
                            ),
                        )

                        # Create new template record
                        from app.models import TemplateCreate, TemplateAuthor

                        template_author = TemplateAuthor(
                            name=template_info.get("author", {}).get("name", "Admin User"),
                            email=template_info.get("author", {}).get("email", ""),
                        )

                        template_create = TemplateCreate(
                            template_id=template_info["id"],
                            name=template_info.get("name", template_info["id"]),
                            version=template_info.get("version", "1.0.0"),
                            description=template_info.get("description", ""),
                            author=template_author,
                            cli_type=template_info.get("cliType", "claude-code"),
                            init_commands=template_info.get("initCommands"),
                        )

                        template_service.create(template_create)
                        synced_count += 1

                    except Exception as e:
                        logger.error(f"Sync template {template_info.get('id')} failed: {e}")
                        continue

                # Complete
                progress_service.set_completed(
                    task_id,
                    result={
                        "message": translate_func("templates.rebuild_success", count=synced_count),
                        "synced_count": synced_count,
                    },
                )
            else:
                progress_service.set_error(
                    task_id,
                    _translate_git_result(translate_func, sync_result) or translate_func("templates.rebuild_scan_failed")
                )
        except Exception as e:
            logger.error(f"Scan template failed: {e}")
            progress_service.set_error(
                task_id,
                translate_func("templates.rebuild_scan_failed")
            )

    except Exception as e:
        logger.error(f"Rebuild template database task failed: {e}")
        progress_service.set_error(
            task_id,
            translate_func("templates.rebuild_task_failed_simple")
        )


def _clone_repository_background(
    task_id: str,
    url: str,
    branch: Optional[str],
    force: bool,
    git_service: TemplateGitService,
    db: Session,
    translate_func,
) -> None:
    """Background task: Clone task"""
    from app.services.task_progress_service import get_task_progress_service, TaskStatus
    from app.services.template_service import TemplateService
    from app.models import TemplateUpdate, TemplateCreate, TemplateAuthor

    progress_service = get_task_progress_service()

    try:
        # Update status to executing
        progress_service.update_progress(
            task_id,
            progress=10,
            message=translate_func("templates.clone_starting"),
            status=TaskStatus.RUNNING,
        )

        # Execution clone
        clone_result = git_service.clone_repository(url=url, branch=branch, force=force)
        success, message = clone_result

        if not success:
            progress_service.set_error(task_id, _translate_git_result(translate_func, clone_result))
            return

        progress_service.update_progress(
            task_id,
            progress=50,
            message=translate_func("templates.clone_complete_scanning")
        )

        # Scan and sync templates to database
        try:
            sync_result = git_service.scan_and_sync_templates()
            sync_success, sync_message, templates = sync_result

            if sync_success and templates:
                template_service = TemplateService(db)
                synced_count = 0
                total_templates = len(templates)

                for idx, template_info in enumerate(templates):
                    try:
                        # Calculate progress (50-95%)
                        progress = 50 + int((idx / total_templates) * 45)
                        progress_service.update_progress(
                            task_id,
                            progress=progress,
                            message=translate_func(
                                "templates.clone_syncing_template",
                                current=idx + 1,
                                total=total_templates,
                                template_id=template_info['id']
                            ),
                        )

                        # Check if template already exists
                        existing = template_service.get(template_info["id"])

                        if existing:
                            # Update existing template
                            update_payload = TemplateUpdate(
                                name=template_info["name"],
                                description=template_info["description"],
                                version=template_info["version"],
                                categoryId=template_info["category"],
                                keywords=template_info["keywords"],
                                status=template_info["status"],
                                author=TemplateAuthor(
                                    name=template_info["author_name"],
                                    email=template_info["author_email"],
                                    url=template_info["author_url"],
                                ),
                            )
                            template_service.update(template_info["id"], update_payload)
                            logger.info(f"Updated template: {template_info['id']}")
                        else:
                            # Create new template
                            create_payload = TemplateCreate(
                                template_id=template_info["id"],
                                name=template_info["name"],
                                description=template_info["description"],
                                version=template_info["version"],
                                keywords=template_info["keywords"],
                                cli_type=template_info["cli_type"],
                                status=template_info["status"],
                                author=TemplateAuthor(
                                    name=template_info["author_name"],
                                    email=template_info["author_email"],
                                    url=template_info["author_url"],
                                ),
                            )
                            template_service.create(create_payload)
                            logger.info(f"Created new template: {template_info['id']}")

                        synced_count += 1
                    except Exception as e:
                        logger.error(f"Sync template {template_info['id']} failed: {e}", exc_info=True)

                # Complete
                result_message = translate_func("templates.clone_success", message=_translate_git_result(translate_func, clone_result), count=synced_count)
                progress_service.set_completed(
                    task_id,
                    result={"message": result_message, "synced_count": synced_count},
                )
            else:
                # Scan failed but clone succeeded
                logger.warning(f"Scan template failed: {sync_message}")
                progress_service.set_completed(
                    task_id,
                    result={"message": _translate_git_result(translate_func, clone_result), "synced_count": 0},
                )

        except Exception as e:
            logger.error(f"Sync template to database failed: {e}", exc_info=True)
            # Even if sync fails, clone succeeded
            progress_service.set_completed(
                task_id,
                result={"message": _translate_git_result(translate_func, clone_result), "synced_count": 0},
            )

    except Exception as e:
        logger.error(f"Clone repository failed: {e}", exc_info=True)
        progress_service.set_error(task_id, _translate_git_exception(translate_func, e))


@router.post(
    "/git/clone",
    response_model=dict,
    summary="Clone Git remote repository (background task)",
    responses=build_responses(401, 422, 500),
)
async def clone_git_repository(
    request: Request,
    payload: GitCloneRequest,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
    db: Session = Depends(get_db),
) -> dict:
    """Clone or update remote Git repository to template center directory (background execution)

    Returns task ID which can be used to query progress
    """
    from app.services.task_progress_service import get_task_progress_service

    progress_service = get_task_progress_service()
    task_id = progress_service.create_task("clone_repository")
    translate = request.state.translate

    # Add background task
    background_tasks.add_task(
        _clone_repository_background,
        task_id=task_id,
        url=payload.url,
        branch=payload.branch,
        force=payload.force,
        git_service=git_service,
        db=db,
        translate_func=translate,
    )

    return {
        "success": True,
        "task_id": task_id,
        "message": translate("templates.clone_submitted"),
    }


@router.get(
    "/git/clone/progress/{task_id}",
    response_model=dict,
    summary="Query clone task progress",
    responses=build_responses(401, 404, 500),
)
async def get_clone_progress(
    request: Request,
    task_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """Query clone task progress"""
    from app.services.task_progress_service import get_task_progress_service

    progress_service = get_task_progress_service()
    task_progress = progress_service.get_progress(task_id)

    if not task_progress:
        translate = request.state.translate
        return {
            "success": False,
            "error": translate("templates.task_not_found"),
        }

    return {
        "success": True,
        "data": task_progress.to_dict(),
    }


@router.get(
    "/git/clone/status",
    response_model=dict,
    summary="Check if repository has been cloned",
    responses=build_responses(401, 500),
)
async def check_clone_status(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> dict:
    """Check if template center repository has been cloned"""
    is_cloned = git_service.is_git_repository()

    status_info = {
        "is_cloned": is_cloned,
    }

    if is_cloned:
        git_status = git_service.get_git_status()
        status_info["remote_url"] = git_status.remote_url
        status_info["current_branch"] = git_status.current_branch

    return {
        "success": True,
        "data": status_info,
    }


@router.post(
    "/rebuild",
    response_model=dict,
    summary="Rebuild database template data (background task)",
    responses=build_responses(401, 500),
)
async def rebuild_templates(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
    db: Session = Depends(get_db),
) -> dict:
    """Rebuild database template data, will delete all old data and recreate from plugin.json (background execution)

    Returns task ID which can be used to query progress
    """
    from app.services.task_progress_service import get_task_progress_service

    translate = request.state.translate

    # Check if already cloned
    if not git_service.is_git_repository():
        return {
            "success": False,
            "error": translate("templates.rebuild_not_cloned"),
        }

    progress_service = get_task_progress_service()
    task_id = progress_service.create_task("rebuild_templates")

    # Add background task
    background_tasks.add_task(
        _rebuild_templates_background,
        task_id=task_id,
        git_service=git_service,
        db=db,
        translate_func=translate,
    )

    return {
        "success": True,
        "task_id": task_id,
        "message": translate("templates.rebuild_submitted"),
    }


@router.get(
    "/rebuild/progress/{task_id}",
    response_model=dict,
    summary="Query rebuild task progress",
    responses=build_responses(401, 404, 500),
)
async def get_rebuild_progress(
    request: Request,
    task_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """Query rebuild task progress"""
    from app.services.task_progress_service import get_task_progress_service

    progress_service = get_task_progress_service()
    task_progress = progress_service.get_progress(task_id)

    if not task_progress:
        translate = request.state.translate
        return {
            "success": False,
            "error": translate("templates.task_not_found"),
        }

    return {
        "success": True,
        "data": task_progress.to_dict(),
    }


# ============ SSH Keys Management API ============


@router.get(
    "/marketplace/ssh-keys",
    summary="Get template center SSH keys",
    responses=build_responses(401, 500),
)
async def get_template_center_ssh_keys(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """Get template center SSH keys information"""
    try:
        ssh_keys = git_service.get_ssh_keys()
        return {
            "success": True,
            "data": ssh_keys,
        }
    except Exception as e:
        logger.error(f"Get SSH keys failed: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": translate("templates.ssh_keys_get_failed"),
        }


@router.post(
    "/marketplace/ssh-keys/generate",
    summary="Generate new SSH key pair",
    responses=build_responses(401, 500),
)
async def generate_template_center_ssh_keys(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """Generate new SSH key pair and save to ~/.ssh directory"""
    try:
        translate = request.state.translate
        ssh_keys = git_service.generate_ssh_keys()
        return {
            "success": True,
            "data": ssh_keys,
            "message": translate("templates.ssh_keys_gen_success")
        }
    except Exception as e:
        logger.error(f"Generate SSH keys failed: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_gen_failed")
        }


@router.put(
    "/marketplace/ssh-keys",
    summary="Update SSH keys",
    responses=build_responses(401, 422, 500),
)
async def update_template_center_ssh_keys(
    request: Request,
    payload: SSHKeysUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """Update template center SSH keys"""
    try:
        translate = request.state.translate
        ssh_keys = git_service.update_ssh_keys(
            private_key=payload.private_key,
            public_key=payload.public_key
        )
        return {
            "success": True,
            "data": ssh_keys,
            "message": translate("templates.ssh_keys_update_success")
        }
    except ValueError as e:
        logger.error(f"Update SSH keys failed (format error): {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_invalid_format")
        }
    except Exception as e:
        logger.error(f"Update SSH keys failed: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_update_failed")
        }


@router.delete(
    "/marketplace/ssh-keys",
    summary="Delete SSH keys",
    responses=build_responses(401, 500),
)
async def delete_template_center_ssh_keys(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """Delete template center SSH keys"""
    try:
        translate = request.state.translate
        git_service.delete_ssh_keys()
        return {
            "success": True,
            "message": translate("templates.ssh_keys_delete_success")
        }
    except Exception as e:
        logger.error(f"Delete SSH keys failed: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_delete_failed")
        }


__all__ = ["router"]
