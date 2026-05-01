"""Celery task definitions: Automated task dispatch and execution"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Iterator, Optional

import httpx
from celery import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.logging import get_celery_logger
from app.db import models as db_models
from app.db.database import SessionLocal
from app.services.automation_execution_logger import AutomationExecutionLogger
from app.services.knowledge_base_maintenance_service import KnowledgeBaseMaintenanceService
from app.services.automation_service import AutomationJobError, AutomationService
from app.utils.datetime_utils import calculate_duration, utcnow

logger = get_celery_logger()

DEFAULT_MODEL = "claude-3-7-sonnet-20250219"
AUTOMATION_PERMISSION_MODE = "bypassPermissions"


@contextmanager
def automation_service() -> Iterator[AutomationService]:
    """Create database session for AutomationService"""

    db = SessionLocal()
    try:
        yield AutomationService(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def knowledge_base_maintenance_service() -> Iterator[KnowledgeBaseMaintenanceService]:
    """Create database session for KnowledgeBaseMaintenanceService"""

    db = SessionLocal()
    try:
        yield KnowledgeBaseMaintenanceService(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _knowledge_base_wiki_index_version_metadata(
    db: Session,
    *,
    user_id: str,
    knowledge_base_id: str | None,
) -> dict[str, Any]:
    if not isinstance(knowledge_base_id, str):
        return {
            "knowledgeBaseId": knowledge_base_id,
            "versionControlEnabled": False,
            "filesChanged": [],
            "commitId": None,
        }

    kb = db.get(db_models.KnowledgeBase, knowledge_base_id)
    version_control_enabled = bool(getattr(kb, "version_control_enabled", False))
    metadata: dict[str, Any] = {
        "knowledgeBaseId": knowledge_base_id,
        "versionControlEnabled": version_control_enabled,
        "filesChanged": [],
        "commitId": None,
    }
    if not version_control_enabled:
        return metadata

    from app.services.knowledge_base_git_service import KnowledgeBaseGitService

    git_service = KnowledgeBaseGitService(db)
    changes = git_service.get_file_changes(user_id=user_id, kb_id=knowledge_base_id)
    files_changed = _version_control_changed_paths(changes)
    metadata["filesChanged"] = files_changed
    if not files_changed:
        return metadata

    try:
        response = git_service.commit_all(
            user_id=user_id,
            kb_id=knowledge_base_id,
            message="Update knowledge base wiki index",
        )
    except ValueError as exc:
        if str(exc) != "GIT_NO_CHANGES":
            raise
        return metadata
    metadata["commitId"] = response.commit.id
    return metadata


def _version_control_changed_paths(changes: Any) -> list[str]:
    paths: dict[str, None] = {}
    for group_name in ("staged", "unstaged", "untracked"):
        for item in getattr(changes, group_name, []) or []:
            path = getattr(item, "path", None)
            if isinstance(path, str) and path:
                paths[path] = None
    return list(paths)


@current_app.task(name="automation.dispatch_due_jobs")
def dispatch_due_jobs(limit: int = 50) -> dict[str, int]:
    """Find due automation tasks and dispatch Celery tasks for execution"""

    dispatched = 0
    with automation_service() as service:
        due_tasks = service.list_due_tasks(limit=limit)
        if not due_tasks:
            return {"dispatched": dispatched}

        for job in due_tasks:
            execution = service.enqueue_execution(
                job.id,
                trigger=job.trigger,
                summary="Automation task added to queue",
            )
            if not execution:
                continue

            dispatched += 1
            current_app.send_task("automation.run_job", args=[job.id, execution.id])

    logger.info("Dispatched %s automation tasks for execution", dispatched)
    return {"dispatched": dispatched}


@current_app.task(name="automation.cleanup_stuck_executions")
def cleanup_stuck_executions(timeout_minutes: int = 60) -> dict[str, int]:
    """Clean up stuck task execution records.

    Mark tasks that are still in running status beyond specified time as failed.

    Args:
        timeout_minutes: Timeout period in minutes, default 60 minutes

    Returns:
        Cleanup statistics
    """
    cleaned = 0
    with automation_service() as service:
        stuck_executions = service.get_stuck_executions(timeout_minutes=timeout_minutes)

        if not stuck_executions:
            return {"cleaned": 0}

        logger.warning(
            "Found %d stuck task execution records, starting cleanup (timeout threshold: %d minutes)",
            len(stuck_executions), timeout_minutes
        )

        for execution in stuck_executions:
            try:
                duration = calculate_duration(execution.started_at) if execution.started_at else timeout_minutes * 60

                service.complete_execution(
                    execution.id,
                    status="failed",
                    summary=f"Task execution timeout (exceeded {timeout_minutes} minutes), automatically cleaned up",
                    error_message="Execution timeout - cleaned up by system",
                    duration=duration,
                    metadata={
                        "error_type": "timeout",
                        "timeout_minutes": timeout_minutes,
                        "cleaned_at": utcnow().isoformat()
                    }
                )
                cleaned += 1

            except Exception as exc:
                logger.error(
                    "Failed to clean up stuck task - execution_id=%s, error=%s",
                    execution.id, str(exc),
                    exc_info=True
                )

        logger.info("Cleanup completed, cleaned %d stuck tasks total", cleaned)
        return {"cleaned": cleaned, "total_stuck": len(stuck_executions)}


@current_app.task(name="knowledge_bases.reconcile_kb_quota")
def reconcile_kb_quota() -> dict[str, int]:
    """Daily reconciliation of knowledge base cached size."""

    with knowledge_base_maintenance_service() as service:
        return service.reconcile_kb_quota()


@current_app.task(name="knowledge_bases.cleanup_tombstoned_kb")
def cleanup_tombstoned_kb() -> dict[str, int]:
    """Clean up tombstoned knowledge bases exceeding retention period."""

    with knowledge_base_maintenance_service() as service:
        return service.cleanup_tombstoned_knowledge_bases()


@current_app.task(name="automation.run_job", bind=True, max_retries=0)
def run_automation_job(self, job_id: str, execution_id: str) -> dict[str, Optional[str]]:
    """Execute automation task: Call Workspace Runtime to start Session

    Args:
        job_id: Automation task ID
        execution_id: Execution record ID

    Returns:
        Execution result dictionary containing status and session_id
    """
    from app.utils.redis_lock import workspace_lock

    logger.debug(
        "Celery task started - task_id=%s, job_id=%s, execution_id=%s",
        self.request.id, job_id, execution_id
    )

    exec_logger: Optional[AutomationExecutionLogger] = None

    try:
        with automation_service() as service:
            job = service.get_job_record(job_id)
            if not job:
                logger.error(
                    "Automation task not found - job_id=%s, execution_id=%s",
                    job_id, execution_id
                )
                service.complete_execution(
                    execution_id,
                    status="failed",
                    summary="Scheduled task not found, execution cancelled",
                    error_message="Scheduled task not found",
                    duration=0,
                    metadata={"error_type": "job_not_found"}
                )
                return {"status": "not_found", "session_id": None}

            exec_logger = AutomationExecutionLogger(
                execution_id=execution_id,
                job_id=job_id,
                workspace_id=job.workspace_id
            )
            exec_logger.info("Automation task started executing", task_name=job.name, prompt_length=len(job.prompt))

            logger.info(
                "Starting automation task execution - job_id=%s, execution_id=%s, workspace_id=%s, prompt=%s",
                job_id, execution_id, job.workspace_id, job.prompt[:100]
            )

            with workspace_lock(job.workspace_id, timeout=3600, blocking=False) as acquired:
                if not acquired:
                    from app.utils.automation_queue import get_queue_manager

                    queue_manager = get_queue_manager()
                    position = queue_manager.enqueue(job.workspace_id, execution_id)

                    exec_logger.info(
                        "Unable to acquire workspace lock, queuing for execution",
                        workspace_id=job.workspace_id,
                        queue_position=position
                    )
                    logger.debug(
                        "Redis queue operation - workspace_id=%s, execution_id=%s, position=%d",
                        job.workspace_id, execution_id, position
                    )

                    service.mark_execution_waiting(
                        execution_id,
                        position=position,
                        summary=f"Queued (position: {position})"
                    )

                    return {"status": "queued", "session_id": None, "queue_position": position}

                exec_logger.info("Successfully acquired workspace lock, starting task execution")
                kb_attachment = None
                if service.is_knowledge_base_wiki_index_job(job):
                    try:
                        kb_attachment = service.validate_knowledge_base_wiki_index_execution(job)
                    except AutomationJobError as exc:
                        exec_logger.error(
                            "Knowledge base wiki index validation failed",
                            reason_code=exc.code,
                            params=exc.params,
                        )
                        service.complete_execution(
                            execution_id,
                            status="failed",
                            summary=f"Knowledge base wiki index validation failed: {exc.code}",
                            duration=0,
                            error_message=exc.code,
                            metadata={
                                **exec_logger.to_metadata(),
                                "reasonCode": exc.code,
                                "knowledgeBaseId": (job.task_metadata or {}).get("knowledgeBaseId"),
                                "workspaceId": job.workspace_id,
                            },
                        )
                        return {"status": "failed", "session_id": None, "error_type": exc.code}

                    from app.utils.redis_lock import knowledge_base_wiki_index_lock

                    with knowledge_base_wiki_index_lock(kb_attachment.kb_id, timeout=3600, blocking=False) as kb_acquired:
                        if not kb_acquired:
                            reason_code = "KB_WIKI_INDEX_LOCK_BUSY"
                            exec_logger.warning(
                                "Knowledge base wiki index lock is busy",
                                knowledge_base_id=kb_attachment.kb_id,
                            )
                            service.complete_execution(
                                execution_id,
                                status="failed",
                                summary="Knowledge base wiki index is already running",
                                duration=0,
                                error_message=reason_code,
                                metadata={
                                    **exec_logger.to_metadata(),
                                    "reasonCode": reason_code,
                                    "knowledgeBaseId": kb_attachment.kb_id,
                                    "workspaceId": job.workspace_id,
                                },
                            )
                            return {"status": "failed", "session_id": None, "error_type": reason_code}

                        return _run_automation_job_with_acquired_locks(
                            service=service,
                            job=job,
                            exec_logger=exec_logger,
                            execution_id=execution_id,
                            kb_mount_alias=kb_attachment.mount_alias,
                        )

                return _run_automation_job_with_acquired_locks(
                    service=service,
                    job=job,
                    exec_logger=exec_logger,
                    execution_id=execution_id,
                    kb_mount_alias=None,
                )

    except Exception as outer_exc:
        logger.critical(
            "Critical error in automation task execution - job_id=%s, execution_id=%s, error=%s",
            job_id, execution_id, str(outer_exc),
            exc_info=True
        )
        return {"status": "error", "session_id": None, "error": str(outer_exc)}
    finally:
        try:
            with automation_service() as service:
                job = service.get_job_record(job_id)
                if job:
                    _trigger_next_queued_task(job.workspace_id)
        except Exception as trigger_exc:
            logger.error(
                "Failed to trigger next queued task - job_id=%s, error=%s",
                job_id, str(trigger_exc),
                exc_info=True
            )


def _run_automation_job_with_acquired_locks(
    *,
    service: AutomationService,
    job: db_models.AutomationJob,
    exec_logger: AutomationExecutionLogger,
    execution_id: str,
    kb_mount_alias: Optional[str],
) -> dict[str, Optional[str]]:
    """Run an automation job after workspace and optional KB locks are acquired."""
    execution = service.mark_execution_running(
        execution_id, summary="Scheduled task executing"
    )
    if not execution:
        exec_logger.error("Execution record not found")
        logger.error(
            "Execution record not found - job_id=%s, execution_id=%s",
            job.id, execution_id
        )
        return {"status": "missing_execution", "session_id": None}

    start_time = execution.started_at or utcnow()
    session_id = None

    try:
        exec_logger.info("Starting task execution")
        session_id, summary, metadata = _execute_automation_job(
            service,
            job,
            exec_logger,
            execution_id,
            kb_mount_alias=kb_mount_alias,
        )

        duration = calculate_duration(start_time)
        exec_logger.info("Task execution successful", session_id=session_id, duration=duration)

        final_metadata = {**metadata, **exec_logger.to_metadata()}

        service.complete_execution(
            execution_id,
            status="success",
            summary=summary,
            duration=duration,
            session_id=session_id,
            metadata=final_metadata,
        )

        logger.info(
            "Automation task execution successful - job_id=%s, execution_id=%s, session_id=%s, duration=%ds",
            job.id, execution_id, session_id, duration
        )
        return {"status": "success", "session_id": session_id}

    except Exception as exc:
        duration = calculate_duration(start_time)
        error_type = type(exc).__name__
        error_message = str(exc)

        if hasattr(exc, 'session_id'):
            session_id = exc.session_id  # type: ignore

        exec_logger.error("TaskExecutionFailed", error_type=error_type, error_message=error_message)
        logger.error(
            "Automation taskExecutionFailed - job_id=%s, execution_id=%s, session_id=%s, "
            "error_type=%s, error=%s, duration=%ds",
            job.id, execution_id, session_id or "N/A",
            error_type, error_message, duration,
            exc_info=True
        )

        try:
            final_metadata = {
                **exec_logger.to_metadata(),
                "error_type": error_type,
                "error_message": error_message,
                "execution_duration": duration,
                "failed_at": utcnow().isoformat(),
                "has_session": session_id is not None,
            }

            service.complete_execution(
                execution_id,
                status="failed",
                summary=f"Scheduled task execution failed ({error_type}): {error_message}",
                duration=duration,
                session_id=session_id,
                error_message=error_message,
                metadata=final_metadata
            )
            logger.info(
                "Execution status updated to failed - execution_id=%s",
                execution_id
            )
        except Exception as update_exc:
            logger.critical(
                "Failed to update execution status! - execution_id=%s, error=%s",
                execution_id, str(update_exc),
                exc_info=True
            )

        return {
            "status": "failed",
            "session_id": session_id,
            "error_type": error_type
        }


def _trigger_next_queued_task(workspace_id: str) -> None:
    """Trigger the next queued task.

    Args:
        workspace_id: Workspace ID
    """
    from app.utils.automation_queue import get_queue_manager

    try:
        queue_manager = get_queue_manager()
        next_execution_id = queue_manager.dequeue(workspace_id)

        if next_execution_id:
            logger.info(
                "Triggering next queued task - workspace_id=%s, execution_id=%s",
                workspace_id, next_execution_id
            )

            db = SessionLocal()
            try:
                execution = db.get(db_models.JobExecution, next_execution_id)
                if execution:
                    run_automation_job.apply_async(
                        args=[execution.job_id, next_execution_id],
                        countdown=1
                    )
                    logger.info(
                        "Next task scheduled - job_id=%s, execution_id=%s",
                        execution.job_id, next_execution_id
                    )
                else:
                    logger.warning(
                        "Execution record not found - execution_id=%s",
                        next_execution_id
                    )
            finally:
                db.close()
        else:
            logger.debug("Queue is empty, no need to trigger next task - workspace_id=%s", workspace_id)

    except Exception as exc:
        logger.error(
            "Failed to trigger next queued task - workspace_id=%s, error=%s",
            workspace_id, str(exc),
            exc_info=True
        )


def _execute_automation_job(
    service: AutomationService,
    job: db_models.AutomationJob,
    exec_logger: AutomationExecutionLogger,
    execution_id: str,
    *,
    kb_mount_alias: Optional[str] = None,
) -> tuple[str, str, dict[str, Any]]:
    """Call workspace runtime to create and execute session

    Args:
        service: AutomationService instance
        job: Automation task record
        exec_logger: Execution logger
        execution_id: Execution record ID

    Returns:
        (session_id, summary, metadata) tuple

    Raises:
        RuntimeError: When execution fails
    """

    db = service.db  # Session managed by AutomationService
    workspace = db.get(db_models.Workspace, job.workspace_id)
    if not workspace:
        exec_logger.error("Workspace not found", workspace_id=job.workspace_id)
        logger.error("Workspace not found - workspace_id=%s", job.workspace_id)
        raise RuntimeError("Corresponding workspace not found")

    user = db.get(db_models.User, job.creator_user_id)
    if not user:
        exec_logger.error("User not found", user_id=job.creator_user_id)
        logger.error("User not found - user_id=%s", job.creator_user_id)
        raise RuntimeError("Corresponding user not found")

    runtime_url = workspace.runtime_internal_url or workspace.runtime_external_url
    if not runtime_url:
        exec_logger.error("Workspace Runtime not started", workspace_name=workspace.name)
        logger.error(
            "Workspace Runtime not started - workspace_id=%s, workspace_name=%s",
            job.workspace_id, workspace.name
        )
        raise RuntimeError("Workspace Runtime not yet started")

    base_url = runtime_url.rstrip("/")
    sessions_url = f"{base_url}/api/v1/agent-sessions"

    # Get internal API token for internal service authentication
    settings = get_settings()
    internal_headers = {
        "X-Internal-Token": settings.INTERNAL_API_TOKEN,
        "Content-Type": "application/json"
    }

    # NOTE: model_key is now determined by the agentic tool on the runtime side.
    # We just select the tool here. Assuming 'claude-code' for automation jobs.
    agentic_tool = "claude-code"
    exec_logger.info("Preparing to create session", runtime_url=base_url, agentic_tool=agentic_tool)
    logger.info(
        "Preparing to create session - workspace_id=%s, runtime_url=%s, agentic_tool=%s",
        job.workspace_id, base_url, agentic_tool
    )

    # Prepare execution parameters
    metadata = job.task_metadata or {}
    images = []
    if isinstance(metadata, dict):
        images_value = metadata.get("images")
        if isinstance(images_value, list):
            images = images_value

    create_payload = _automation_session_create_payload(
        workspace_id=job.workspace_id,
        agentic_tool=agentic_tool,
        workspace_path=f"/knowledge/{kb_mount_alias}" if kb_mount_alias else None,
    )

    effective_prompt = (
        service.build_knowledge_base_wiki_index_prompt(mount_alias=kb_mount_alias)
        if kb_mount_alias
        else job.prompt
    )

    prompt_payload = {
        "prompt": effective_prompt,
        "images": images,
        "stream": True,  # Streaming is handled by the pub/sub wait
        "permission_mode": AUTOMATION_PERMISSION_MODE,
        "automation_execution_id": execution_id,  # For completion notification
    }

    session_id = None

    try:
        with httpx.Client(timeout=60.0) as client:
            # Step 1: Create Session
            try:
                exec_logger.info("SendCreate Session Request", url=sessions_url)
                logger.info(
                    "SendCreate Session Request - url=%s, workspace_id=%s",
                    sessions_url, job.workspace_id
                )
                response = client.post(sessions_url, json=create_payload, headers=internal_headers)
                response.raise_for_status()
                session_data = response.json()
                session_id = session_data["session_id"]
                exec_logger.info("Session created successfully", session_id=session_id)
                logger.info(
                    "Session created successfully - session_id=%s, workspace_id=%s",
                    session_id, job.workspace_id
                )
            except httpx.HTTPStatusError as e:
                error_detail = _extract_http_error_detail(e)
                exec_logger.error("Failed to create session", status_code=e.response.status_code, error=error_detail)
                logger.error(
                    "Failed to create session - status_code=%s, error=%s, url=%s",
                    e.response.status_code, error_detail, sessions_url
                )
                raise RuntimeError(
                    f"Failed to create session (HTTP {e.response.status_code}): {error_detail}"
                ) from e
            except httpx.RequestError as e:
                exec_logger.error("Unable to connect to Workspace Runtime", error=str(e))
                logger.error(
                    "Unable to connect to Workspace Runtime - error=%s, url=%s",
                    str(e), sessions_url
                )
                raise RuntimeError(f"Unable to connect to Workspace Runtime: {e}") from e

            # Step 2: Execute command (async, return immediately)
            try:
                execute_url = f"{sessions_url}/{session_id}/prompt" # Changed from /execute to /prompt
                exec_logger.info("SendExecution Prompt Request", session_id=session_id, execution_id=execution_id)
                logger.info(
                    "SendExecution Prompt Request - url=%s, session_id=%s, execution_id=%s",
                    execute_url, session_id, execution_id
                )
                response = client.post(execute_url, json=prompt_payload, headers=internal_headers)
                response.raise_for_status()
                exec_logger.info("Execution prompt request sent (async execution)", session_id=session_id)
                logger.info(
                    "Execution prompt request sent (async execution) - session_id=%s",
                    session_id
                )
            except httpx.HTTPStatusError as e:
                error_detail = _extract_http_error_detail(e)
                logger.error(
                    "Execution prompt failed - status_code=%s, error=%s, session_id=%s",
                    e.response.status_code, error_detail, session_id
                )
                raise RuntimeError(
                    f"Execution prompt failed (HTTP {e.response.status_code}): {error_detail}"
                ) from e
            except httpx.RequestError as e:
                logger.error(
                    "Execution request failed - error=%s, session_id=%s",
                    str(e), session_id
                )
                raise RuntimeError(f"Execution request failed: {e}") from e

        # Step 3: Wait for execution completion (via Redis Pub/Sub)
        from app.utils.redis_subscriber import wait_for_execution_completed_sync

        exec_logger.info("Waiting for execution completion", execution_id=execution_id, timeout=3600)
        logger.info(
            "Waiting for execution completion - execution_id=%s, timeout=3600s",
            execution_id
        )

        # NOTE: This relies on the new execution_service publishing a compatible message.
        execution_result = wait_for_execution_completed_sync(
            execution_id=execution_id,
            timeout=3600  # 1 hour timeout
        )

        if not execution_result:
            raise RuntimeError("Waiting for execution completion timed out (1 hour)")

        exec_logger.info("Received execution completion event", execution_id=execution_id, result=execution_result)
        logger.info(
            "Received execution completion event - execution_id=%s, status=%s, total_messages=%d",
            execution_id, execution_result.get("status"), execution_result.get("total_messages", 0)
        )

        # CheckExecutionStatus
        exec_status = execution_result.get("status")
        has_error = execution_result.get("has_error", False)
        error_message = execution_result.get("error_message")
        total_messages = execution_result.get("total_messages", 0)

        if exec_status == "failed" or has_error:
            error_msg = error_message or "Execution failed"
            raise RuntimeError(f"Scheduled task execution failed: {error_msg}")

        if exec_status == "aborted":
            raise RuntimeError("Scheduled task execution was aborted")

        # Step 4: Get execution result message
        # This part of the logic might need adjustment if the message structure from the new agent_session is different.
        # For now, we assume it's compatible enough to find a summary.
        messages_url = f"{base_url}/api/v1/sessions/{session_id}/messages"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(messages_url, params={"limit": 100})
                response.raise_for_status()
                messages_data = response.json()
                messages = messages_data.get("items", [])
                logger.info(
                    "Retrieved execution result messages - session_id=%s, message_count=%d",
                    session_id, len(messages)
                )
        except Exception as e:
            logger.warning(f"Failed to retrieve execution result messages: {e}")
            messages = []

        # Find result message
        # This logic is highly dependent on the old message format.
        # The new format uses Content Blocks. This will likely fail or return a poor summary.
        # TODO: Re-implement summary extraction based on AgentMessage format.
        summary = "Scheduled task execution completed"
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, dict) and last_message.get("content"):
                # Try to find a text block in the last assistant message
                if last_message.get("role") == "assistant" and isinstance(last_message.get("content"), list):
                    text_blocks = [block for block in last_message["content"] if block.get("type") == "text"]
                    if text_blocks and text_blocks[0].get("text"):
                        summary = text_blocks[0]["text"]

        metadata_out = {
            "totalMessages": total_messages,
            "lastMessageId": (
                messages[-1].get("message_id")
                if messages and isinstance(messages[-1], dict)
                else None
            ),
            "hasErrorMessage": has_error,
            "isError": False,
        }
        if kb_mount_alias:
            metadata = job.task_metadata or {}
            knowledge_base_id = metadata.get("knowledgeBaseId") if isinstance(metadata, dict) else None
            metadata_out.update(
                _knowledge_base_wiki_index_version_metadata(
                    db,
                    user_id=job.creator_user_id,
                    knowledge_base_id=knowledge_base_id,
                )
            )

        return session_id, summary, metadata_out

    except Exception as e:
        # If session already created, attach session_id to exception
        if session_id:
            # Create new exception and attach session_id
            error_with_session = RuntimeError(str(e))
            error_with_session.session_id = session_id  # type: ignore
            raise error_with_session from e
        else:
            raise


def _automation_session_create_payload(
    *,
    workspace_id: str,
    agentic_tool: str,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Build the runtime session payload for scheduled automation."""
    payload = {
        "workspace_id": workspace_id,
        "agentic_tool": agentic_tool,
        "source": "automation",
        "permission_config": {"mode": AUTOMATION_PERMISSION_MODE},
    }
    if workspace_path is not None:
        payload["workspace_path"] = workspace_path
    return payload


def _extract_http_error_detail(error: httpx.HTTPStatusError) -> str:
    """Extract detailed information from HTTP error response"""
    try:
        error_data = error.response.json()
        if isinstance(error_data, dict):
            return error_data.get("detail", str(error))
    except Exception:
        pass
    return str(error)


@current_app.task(name="automation.cleanup_expired_queue")
def cleanup_expired_queue() -> dict:
    """Clean up timed out queued tasks

    Executed periodically (every 5 minutes) to clean up timed-out queued tasks across all workspaces.

    Returns:
        Cleanup result dictionary
    """
    logger.info("Starting cleanup of timed-out queued tasks")

    from app.utils.automation_queue import get_queue_manager

    db = SessionLocal()
    try:
        service = AutomationService(db)
        queue_manager = get_queue_manager()

        # Query all workspaces with queued tasks
        stmt = select(db_models.AutomationJob.workspace_id).distinct().where(
            db_models.AutomationJob.status == "active"
        )
        workspace_ids = db.execute(stmt).scalars().all()

        total_cleaned = 0
        total_timeout = 0

        for workspace_id in workspace_ids:
            # Get workspace queue configuration (use first active job's configuration)
            job = db.execute(
                select(db_models.AutomationJob).where(
                    db_models.AutomationJob.workspace_id == workspace_id,
                    db_models.AutomationJob.status == "active"
                ).limit(1)
            ).scalar_one_or_none()

            if not job:
                continue

            timeout_seconds = job.queue_timeout

            # Clean up timed out tasks in Redis
            cleaned = queue_manager.cleanup_expired(workspace_id, timeout_seconds)
            total_cleaned += cleaned

            if cleaned > 0:
                logger.warning(
                    "Cleaned up timed-out queued tasks - workspace_id=%s, cleaned=%d, timeout=%ds",
                    workspace_id, cleaned, timeout_seconds
                )

            # Query tasks with waiting status timeout in database
            from app.utils.datetime_utils import utcnow
            cutoff_time = utcnow() - timedelta(seconds=timeout_seconds)

            timeout_executions = db.execute(
                select(db_models.JobExecution).where(
                    db_models.JobExecution.job_id.in_(
                        select(db_models.AutomationJob.id).where(
                            db_models.AutomationJob.workspace_id == workspace_id
                        )
                    ),
                    db_models.JobExecution.status == "waiting",
                    db_models.JobExecution.queued_at < cutoff_time
                )
            ).scalars().all()

            for execution in timeout_executions:
                execution.status = "timeout"
                execution.summary = f"Queue timeout (exceeded {timeout_seconds} seconds)"
                execution.finished_at = utcnow()
                execution.duration = calculate_duration(execution.queued_at) if execution.queued_at else 0
                execution.updated_at = utcnow()
                total_timeout += 1

                logger.warning(
                    "Marking queued task as timed out - execution_id=%s, queued_at=%s",
                    execution.id, execution.queued_at
                )

            db.commit()

        logger.info(
            "Cleanup of timed-out queued tasks completed - total_cleaned=%d, total_timeout=%d",
            total_cleaned, total_timeout
        )

        return {
            "status": "success",
            "total_cleaned": total_cleaned,
            "total_timeout": total_timeout,
            "workspaces_checked": len(workspace_ids)
        }

    except Exception as exc:
        logger.error(
            "Failed to clean up timed-out queued tasks - error=%s",
            str(exc),
            exc_info=True
        )
        db.rollback()
        return {
            "status": "error",
            "error": str(exc)
        }
    finally:
        db.close()


__all__ = [
    "dispatch_due_jobs",
    "run_automation_job",
    "cleanup_expired_queue",
]
