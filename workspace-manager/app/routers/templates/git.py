"""模板 Git 版本控制和 SSH Keys 管理路由"""

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
    if message in {"SSH_PRIVATE_KEY_INVALID", "SSH_PUBLIC_KEY_INVALID", "私鑰格式不正確", "公鑰格式不正確"}:
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
    """取得模板 Git 服務實例"""
    return TemplateGitService()


# ============ Git 版本控制 API ============


@router.get(
    "/git/repository/status",
    response_model=GitRepositoryStatus,
    summary="取得 Template Center Git 倉庫初始化狀態",
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
    summary="初始化 Template Center Git 倉庫",
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
        logger.error(f"初始化 Template Center Git 倉庫失敗: {e}")
        return GitOperationResponse(
            success=False,
            message=translate("templates.git.repository_init_failed"),
            error=_translate_git_exception(translate, e),
        )


@router.get(
    "/git/version-control/status",
    response_model=TemplateVersionControlStatus,
    summary="取得 Template Center file-level Git 狀態",
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
    summary="取得 Template Center file-level Git 變更",
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
    summary="取得 Template Center Git 分支列表",
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
    summary="切換或建立 Template Center Git 分支",
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
    summary="暫存 Template Center Git 檔案",
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
    summary="取消暫存 Template Center Git 檔案",
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
    summary="捨棄 Template Center Git 檔案變更",
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
    summary="提交 Template Center Git 變更",
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
    summary="列出 Template Center Git 提交歷史",
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
    summary="取得 Template Center Git 提交檔案",
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
    summary="取得 Template Center Git 檔案差異",
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
    summary="讀取 Template Center Git 檔案內容",
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
    summary="Fetch Template Center Git 遠端引用",
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
    summary="Pull Template Center Git 遠端變更",
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
    summary="Push Template Center Git 變更",
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
    summary="取得 Git 使用者資訊",
    responses=build_responses(401, 500),
)
async def get_git_user_config(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
) -> GitUserConfigResponse:
    """取得 git config --global 設定的使用者資訊"""

    try:
        config = git_service.get_user_config()
        return GitUserConfigResponse(success=True, data=config)
    except Exception as e:
        logger.error(f"取得 Git 使用者資訊失敗: {e}")
        translate = request.state.translate
        return GitUserConfigResponse(
            success=False,
            error=translate("templates.git_user_config_get_failed")
        )


@router.post(
    "/git/user-config",
    response_model=GitOperationResponse,
    summary="更新 Git 使用者資訊",
    responses=build_responses(401, 422, 500),
)
async def update_git_user_config(
    request: Request,
    payload: GitUserConfig,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
) -> GitOperationResponse:
    """更新 git config --global 的使用者資訊"""

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
        logger.error(f"更新 Git 使用者資訊失敗: {e}")
        translate = request.state.translate
        return GitOperationResponse(
            success=False,
            message=translate("templates.git_user_config_update_failed"),
            error=_translate_git_exception(translate, e)
        )


@router.post(
    "/git/remote-url",
    response_model=GitOperationResponse,
    summary="設定 Git 遠端倉庫 URL",
    responses=build_responses(401, 422, 500),
)
async def set_git_remote_url(
    request: Request,
    payload: GitRemoteUrlRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
) -> GitOperationResponse:
    """設定或更新 Git 遠端倉庫 URL (origin)"""

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
        logger.error(f"設定遠端倉庫 URL 失敗: {e}")
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
    """後台執行重建模板資料庫任務"""
    from app.services.task_progress_service import get_task_progress_service, TaskStatus
    from app.services.template_service import TemplateService
    from sqlalchemy import text

    progress_service = get_task_progress_service()

    try:
        # 更新狀態為執行中
        progress_service.update_progress(
            task_id,
            progress=10,
            message=translate_func("templates.rebuild_clearing_data"),
            status=TaskStatus.RUNNING,
        )

        # 清除所有舊的模板資料
        try:
            db.execute(text("DELETE FROM templates"))
            db.commit()
            logger.info("已清除所有舊的模板資料")
        except Exception as e:
            logger.error(f"清除模板資料失敗: {e}")
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

        # 掃描並同步模板到資料庫
        try:
            sync_result = git_service.scan_and_sync_templates()
            sync_success, sync_message, templates = sync_result

            if sync_success and templates:
                template_service = TemplateService(db)
                synced_count = 0
                total_templates = len(templates)

                for idx, template_info in enumerate(templates):
                    try:
                        # 計算進度 (30-95%)
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

                        # 建立新的模板記錄
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
                        logger.error(f"同步模板 {template_info.get('id')} 失敗: {e}")
                        continue

                # 完成
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
            logger.error(f"掃描模板失敗: {e}")
            progress_service.set_error(
                task_id,
                translate_func("templates.rebuild_scan_failed")
            )

    except Exception as e:
        logger.error(f"重建模板資料庫任務失敗: {e}")
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
    """後台執行 clone 任務"""
    from app.services.task_progress_service import get_task_progress_service, TaskStatus
    from app.services.template_service import TemplateService
    from app.models import TemplateUpdate, TemplateCreate, TemplateAuthor

    progress_service = get_task_progress_service()

    try:
        # 更新狀態為執行中
        progress_service.update_progress(
            task_id,
            progress=10,
            message=translate_func("templates.clone_starting"),
            status=TaskStatus.RUNNING,
        )

        # 執行 clone
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

        # 掃描並同步模板到資料庫
        try:
            sync_result = git_service.scan_and_sync_templates()
            sync_success, sync_message, templates = sync_result

            if sync_success and templates:
                template_service = TemplateService(db)
                synced_count = 0
                total_templates = len(templates)

                for idx, template_info in enumerate(templates):
                    try:
                        # 計算進度 (50-95%)
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

                        # 檢查模板是否已存在
                        existing = template_service.get(template_info["id"])

                        if existing:
                            # 更新現有模板
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
                            logger.info(f"已更新模板: {template_info['id']}")
                        else:
                            # 建立新模板
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
                            logger.info(f"已建立新模板: {template_info['id']}")

                        synced_count += 1
                    except Exception as e:
                        logger.error(f"同步模板 {template_info['id']} 失敗: {e}", exc_info=True)

                # 完成
                result_message = translate_func("templates.clone_success", message=_translate_git_result(translate_func, clone_result), count=synced_count)
                progress_service.set_completed(
                    task_id,
                    result={"message": result_message, "synced_count": synced_count},
                )
            else:
                # 掃描失敗但 clone 成功
                logger.warning(f"掃描模板失敗: {sync_message}")
                progress_service.set_completed(
                    task_id,
                    result={"message": _translate_git_result(translate_func, clone_result), "synced_count": 0},
                )

        except Exception as e:
            logger.error(f"同步模板到資料庫失敗: {e}", exc_info=True)
            # 即使同步失敗，clone 已成功
            progress_service.set_completed(
                task_id,
                result={"message": _translate_git_result(translate_func, clone_result), "synced_count": 0},
            )

    except Exception as e:
        logger.error(f"Clone 倉庫失敗: {e}", exc_info=True)
        progress_service.set_error(task_id, _translate_git_exception(translate_func, e))


@router.post(
    "/git/clone",
    response_model=dict,
    summary="Clone Git 遠端倉庫（後台任務）",
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
    """Clone 或更新遠端 Git 倉庫到模板中心目錄（後台執行）

    返回任務 ID，可用於查詢進度
    """
    from app.services.task_progress_service import get_task_progress_service

    progress_service = get_task_progress_service()
    task_id = progress_service.create_task("clone_repository")
    translate = request.state.translate

    # 添加後台任務
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
    summary="查詢 Clone 任務進度",
    responses=build_responses(401, 404, 500),
)
async def get_clone_progress(
    request: Request,
    task_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """查詢 Clone 任務的進度"""
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
    summary="檢查倉庫是否已 Clone",
    responses=build_responses(401, 500),
)
async def check_clone_status(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
) -> dict:
    """檢查模板中心倉庫是否已 clone"""
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
    summary="重建資料庫模板資料（後台任務）",
    responses=build_responses(401, 500),
)
async def rebuild_templates(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service),
    db: Session = Depends(get_db),
) -> dict:
    """重建資料庫模板資料，會刪除所有舊資料並從 plugin.json 重新建立（後台執行）

    返回任務 ID，可用於查詢進度
    """
    from app.services.task_progress_service import get_task_progress_service

    translate = request.state.translate

    # 檢查是否已 clone
    if not git_service.is_git_repository():
        return {
            "success": False,
            "error": translate("templates.rebuild_not_cloned"),
        }

    progress_service = get_task_progress_service()
    task_id = progress_service.create_task("rebuild_templates")

    # 添加後台任務
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
    summary="查詢重建任務進度",
    responses=build_responses(401, 404, 500),
)
async def get_rebuild_progress(
    request: Request,
    task_id: str,
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    """查詢重建任務的進度"""
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


# ============ SSH Keys 管理 API ============


@router.get(
    "/marketplace/ssh-keys",
    summary="取得模板中心的 SSH Keys",
    responses=build_responses(401, 500),
)
async def get_template_center_ssh_keys(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """取得模板中心的 SSH Keys 資訊"""
    try:
        ssh_keys = git_service.get_ssh_keys()
        return {
            "success": True,
            "data": ssh_keys,
        }
    except Exception as e:
        logger.error(f"取得 SSH Keys 失敗: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": translate("templates.ssh_keys_get_failed"),
        }


@router.post(
    "/marketplace/ssh-keys/generate",
    summary="產生新的 SSH Key Pair",
    responses=build_responses(401, 500),
)
async def generate_template_center_ssh_keys(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """產生新的 SSH Key Pair 並儲存到 ~/.ssh 目錄"""
    try:
        translate = request.state.translate
        ssh_keys = git_service.generate_ssh_keys()
        return {
            "success": True,
            "data": ssh_keys,
            "message": translate("templates.ssh_keys_gen_success")
        }
    except Exception as e:
        logger.error(f"產生 SSH Keys 失敗: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_gen_failed")
        }


@router.put(
    "/marketplace/ssh-keys",
    summary="更新 SSH Keys",
    responses=build_responses(401, 422, 500),
)
async def update_template_center_ssh_keys(
    request: Request,
    payload: SSHKeysUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """更新模板中心的 SSH Keys"""
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
        logger.error(f"更新 SSH Keys 失敗（格式錯誤）: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_invalid_format")
        }
    except Exception as e:
        logger.error(f"更新 SSH Keys 失敗: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_update_failed")
        }


@router.delete(
    "/marketplace/ssh-keys",
    summary="刪除 SSH Keys",
    responses=build_responses(401, 500),
)
async def delete_template_center_ssh_keys(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    git_service: TemplateGitService = Depends(get_template_git_service)
):
    """刪除模板中心的 SSH Keys"""
    try:
        translate = request.state.translate
        git_service.delete_ssh_keys()
        return {
            "success": True,
            "message": translate("templates.ssh_keys_delete_success")
        }
    except Exception as e:
        logger.error(f"刪除 SSH Keys 失敗: {e}")
        translate = request.state.translate
        return {
            "success": False,
            "error": _translate_git_exception(translate, e),
            "message": translate("templates.ssh_keys_delete_failed")
        }


__all__ = ["router"]
