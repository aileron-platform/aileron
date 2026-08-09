from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from typing import Any, Never
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.thread.domain.enums import (
    RUNTIME_RESTART_RECONCILIATION_STATUSES,
    RUNNING_STATUSES,
    ThreadStatus,
)
from app.modules.thread.domain.tool_names import (
    QUESTION_EXPIRED_ALREADY_ANSWERED,
    QUESTION_EXPIRED_CODE,
    QUESTION_EXPIRED_NOT_DELIVERED,
    QUESTION_EXPIRED_QUEUED_MESSAGES,
    QUESTION_EXPIRED_SUPERSEDED,
    QUESTION_TOOL_NAME,
)
from app.modules.thread.persistence_models import (
    ThreadMessageModel,
    ThreadModel,
    ThreadTurnExecutionModel,
    ThreadTurnModel,
)
from app.modules.thread.message_repository import (
    ThreadMessageRepository,
)
from app.modules.thread.repository import (
    ThreadDeleteResult,
    ThreadRepository,
)
from app.modules.thread.turn_repository import ThreadTurnRepository
from app.modules.thread.api_models import (
    ThreadDetailResponse,
    ThreadExecutionMetadataResponse,
    ThreadMutationResponse,
    ThreadTimelinePageResponse,
    ThreadTurnMetadataResponse,
    ThreadSummaryResponse,
    TimelineInteractionAnswerResponse,
    TimelineItemsResponse,
    TimelineMessageItemResponse,
    TimelinePageInfoResponse,
    TimelineToolCallResponse,
    TimelineToolResultResponse,
)
from app.modules.thread.capabilities_store import CapabilitiesStore
from app.modules.thread.execution import (
    AgentRunner,
    AsyncSessionFactory,
    InvalidationSink,
    _ThreadExecution,
)
from app.modules.thread.invalidation_emitter import (
    get_thread_invalidation_emitter,
)
from app.modules.thread.agent_runner_factory import get_agent_runner
from app.modules.thread.attachments import (
    ThreadAttachmentService,
)
from app.modules.runtime_control.state import (
    RuntimeDrainingError,
    get_runtime_admission_state,
)
from app.modules.thread.state_changes import apply_thread_error

UNTITLED_THREAD_TITLE_KEY = "aiChat.thread.untitled"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThreadApiError(Exception):
    status_code: int
    error_code: str
    error_info: dict


class ThreadService:
    """Thread API application service."""

    def __init__(
        self,
        db: AsyncSession,
        workspace_id: str,
        runner: AgentRunner | None = None,
        invalidation_sink: InvalidationSink | None = None,
        attachment_service: ThreadAttachmentService | None = None,
        event_session_factory: AsyncSessionFactory | None = None,
    ) -> None:
        self.db = db
        self.workspace_id = workspace_id
        self.thread_repo = ThreadRepository(db, workspace_id=workspace_id)
        self.message_repo = ThreadMessageRepository(db)
        self.turn_repo = ThreadTurnRepository(db)
        self.capabilities_store = CapabilitiesStore()
        self._execution = _ThreadExecution(
            db=db,
            workspace_id=workspace_id,
            thread_repo=self.thread_repo,
            message_repo=self.message_repo,
            capabilities_store=self.capabilities_store,
            runner=runner or get_agent_runner(workspace_id),
            invalidation_sink=invalidation_sink or get_thread_invalidation_emitter(),
            attachment_service=attachment_service,
            event_session_factory=event_session_factory,
        )
        self.invalidation_sink = invalidation_sink or get_thread_invalidation_emitter()
        self.event_session_factory = event_session_factory

    async def list_threads(
        self, user_id: str, archived: bool
    ) -> list[ThreadSummaryResponse]:
        threads = await self.thread_repo.list_for_user(
            user_id=user_id, archived=archived
        )
        threads = [
            await self._reconcile_stale_running_thread(thread) for thread in threads
        ]
        return [self._to_summary(thread) for thread in threads]

    async def create_draft(
        self,
        *,
        user_id: str,
        agentic_tool: str,
        model: str,
        claude_mode: str | None,
    ) -> ThreadDetailResponse:
        self._require_runtime_action()
        capabilities = await self.capabilities_store.get(self.db, self.workspace_id)
        if capabilities is None:
            raise ThreadApiError(
                status_code=409,
                error_code="capabilities_unavailable",
                error_info={"workspace_id": self.workspace_id},
            )
        if not capabilities.validate_selection(agentic_tool, model, claude_mode):
            raise ThreadApiError(
                status_code=422,
                error_code="invalid_tool_selection",
                error_info={
                    "agentic_tool": agentic_tool,
                    "model": model,
                    "claude_mode": claude_mode,
                },
            )

        thread = await self.thread_repo.create(
            ThreadModel(
                id=str(uuid4()),
                workspace_id=self.workspace_id,
                user_id=user_id,
                origin="user",
                title="",
                agentic_tool=agentic_tool,
                model=model,
                claude_mode=claude_mode,
                status=ThreadStatus.DRAFT.value,
                queued_messages=[],
                draft_message=None,
                archived=False,
            )
        )
        await self.invalidation_sink.emit(
            user_id,
            self.workspace_id,
            thread.id,
            "thread_created",
        )
        return await self._to_detail(thread)

    async def create_or_get_automation_thread(
        self,
        *,
        automation_job_id: str,
        automation_execution_id: str,
        user_id: str,
        git_context_id: str,
        agentic_tool: str,
        model: str,
        agent_mode: str | None,
    ) -> ThreadDetailResponse:
        self._require_runtime_action()
        thread = await self.thread_repo.create_or_get_automation(
            ThreadModel(
                id=str(uuid4()),
                workspace_id=self.workspace_id,
                user_id=user_id,
                origin="automation",
                automation_job_id=automation_job_id,
                automation_execution_id=automation_execution_id,
                title="",
                agentic_tool=agentic_tool,
                model=model,
                claude_mode=agent_mode,
                status=ThreadStatus.DRAFT.value,
                queued_messages=[],
                draft_message=None,
                git_context_id=git_context_id,
                archived=False,
            )
        )
        return await self._to_detail(thread)

    async def get_by_automation_execution(
        self, *, automation_execution_id: str, user_id: str
    ) -> ThreadDetailResponse:
        thread = await self.thread_repo.get_by_automation_execution(
            automation_execution_id
        )
        if thread is None:
            raise ThreadApiError(
                404,
                "automation_thread_not_found",
                {"automation_execution_id": automation_execution_id},
            )
        return await self._to_detail(thread)

    async def prepare_automation_execution(
        self,
        *,
        thread_id: str,
        message: dict[str, Any],
        execution_id: str,
        permission_mode: str | None,
    ) -> None:
        """Persist an automation execution before its provider process starts."""
        await self._execution.prepare_submission(
            thread_id,
            message,
            execution_id=execution_id,
            permission_mode=permission_mode,
        )

    async def start_automation_execution(
        self,
        *,
        thread_id: str,
        execution_id: str,
        permission_mode: str | None,
    ) -> None:
        """Start a prepared automation execution through the runner seam."""
        await self._execution.start_prepared_submission(
            thread_id=thread_id,
            execution_id=execution_id,
            permission_mode=permission_mode,
        )

    async def wait_for_execution(self, execution_id: str) -> None:
        await self._execution.wait(execution_id)

    async def stop_execution(self, execution_id: str) -> None:
        await self._execution.stop(execution_id)

    async def stop_and_confirm_execution(self, execution_id: str) -> None:
        await self._execution.stop_and_confirm(execution_id)

    def execution_is_alive(self, execution_id: str) -> bool:
        return self._execution.is_alive(execution_id)

    async def update_draft(
        self,
        *,
        thread_id: str,
        user_id: str,
        patch: dict[str, Any],
    ) -> ThreadDetailResponse:
        self._require_runtime_action()
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        if self._is_locked_thread_patch(thread, patch):
            raise ThreadApiError(409, "thread_locked", {"thread_id": thread_id})

        selection_keys = {"agentic_tool", "model", "claude_mode"}
        resolved_model = None
        if selection_keys.intersection(patch):
            resolved_model = await self._resolve_allowed_model(
                agentic_tool=patch.get("agentic_tool", thread.agentic_tool),
                requested_model=patch.get("model", thread.model),
                claude_mode=patch.get("claude_mode", thread.claude_mode),
            )

        def mutate(model: ThreadModel) -> None:
            if self._is_locked_thread_patch(model, patch):
                raise ThreadApiError(409, "thread_locked", {"thread_id": thread_id})

            agentic_tool = patch.get("agentic_tool", model.agentic_tool)
            selected_model = resolved_model or model.model
            claude_mode = patch.get("claude_mode", model.claude_mode)

            if "agentic_tool" in patch:
                model.agentic_tool = agentic_tool
            if resolved_model is not None:
                model.model = selected_model
            if "claude_mode" in patch:
                model.claude_mode = claude_mode
            if "draft_message" in patch:
                model.draft_message = patch["draft_message"]

        updated = await self.thread_repo.locked_update(thread_id, mutate)
        if updated is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        await self._emit_for_thread(updated, "messages_updated")
        return await self._to_detail(updated)

    @staticmethod
    def _is_locked_thread_patch(thread: ThreadModel, patch: dict[str, Any]) -> bool:
        if thread.status == ThreadStatus.DRAFT.value:
            return False
        if "draft_message" in patch:
            return True
        next_agentic_tool = patch.get("agentic_tool")
        return (
            isinstance(next_agentic_tool, str)
            and next_agentic_tool != thread.agentic_tool
        )

    async def get_thread(self, thread_id: str, user_id: str) -> ThreadDetailResponse:
        thread = await self.thread_repo.get_readable(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        thread = await self._reconcile_stale_running_thread(thread)
        return await self._to_detail(thread)

    async def list_timeline(
        self,
        *,
        thread_id: str,
        user_id: str,
        before_sequence: int | None,
        limit: int,
    ) -> ThreadTimelinePageResponse:
        thread = await self.thread_repo.get_readable(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        page_limit = min(max(limit, 1), 200)
        anchors = await self.message_repo.list_timeline_anchors(
            thread_id,
            before_sequence=before_sequence,
            limit=page_limit + 1,
        )
        has_more = len(anchors) > page_limit
        visible = anchors[-page_limit:] if has_more else anchors
        projected = await self._project_timeline(thread_id, visible)
        oldest_sequence = visible[0].message_sequence if visible else None
        newest_sequence = visible[-1].message_sequence if visible else None
        return ThreadTimelinePageResponse(
            items=projected.items,
            turns=projected.turns,
            executions=projected.executions,
            pageInfo=TimelinePageInfoResponse(
                oldestSequence=oldest_sequence,
                newestSequence=newest_sequence,
                nextBeforeSequence=oldest_sequence if has_more else None,
                hasMoreBefore=has_more,
            ),
        )

    async def get_timeline_items(
        self, *, thread_id: str, item_ids: list[str], user_id: str
    ) -> TimelineItemsResponse:
        thread = await self.thread_repo.get_readable(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        unique_ids = list(dict.fromkeys(item_ids))
        if len(unique_ids) > 200:
            raise ThreadApiError(422, "timeline_item_limit_exceeded", {"limit": 200})
        try:
            parsed_ids = [int(item_id) for item_id in unique_ids]
        except ValueError as exc:
            raise ThreadApiError(422, "invalid_timeline_item_id", {}) from exc
        anchors = await self.message_repo.get_timeline_anchors_by_ids(
            thread_id, parsed_ids
        )
        if len(anchors) != len(parsed_ids):
            raise ThreadApiError(404, "timeline_item_not_found", {})
        return await self._project_timeline(thread_id, anchors)

    async def get_tool_result_content(
        self, *, thread_id: str, message_id: int, user_id: str
    ) -> tuple[str, bytes]:
        thread = await self.thread_repo.get_readable(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        message = await self.message_repo.get_for_thread(thread_id, message_id)
        if message is None or message.type != "tool_result":
            raise ThreadApiError(
                404, "tool_result_not_found", {"message_id": message_id}
            )
        stored = await self.message_repo.get_tool_result_content(message_id)
        if stored is not None:
            return stored.media_type, stored.payload
        preview = message.content.get("preview", "")
        media_type = str(
            message.content.get("mediaType") or "text/plain; charset=utf-8"
        )
        return media_type, str(preview).encode("utf-8")

    async def submit_thread(
        self,
        *,
        thread_id: str,
        user_id: str,
        message: dict,
    ) -> ThreadMutationResponse:
        self._require_runtime_action()
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        if thread.status != ThreadStatus.DRAFT.value:
            raise ThreadApiError(409, "thread_locked", {"thread_id": thread_id})
        agentic_tool = thread.agentic_tool
        model = thread.model
        claude_mode = thread.claude_mode
        resolved_model = await self._resolve_allowed_model(
            agentic_tool=agentic_tool,
            requested_model=model,
            claude_mode=claude_mode,
        )

        try:
            updated = await self._submit_with_resolved_model(
                thread=thread,
                original_model=model,
                resolved_model=resolved_model,
                message=message,
            )
        except ValueError as exc:
            if str(exc) == "capabilities_unavailable":
                raise ThreadApiError(
                    409,
                    "capabilities_unavailable",
                    {"workspace_id": self.workspace_id},
                ) from exc
            if str(exc) == "invalid_tool_selection":
                raise ThreadApiError(
                    409,
                    "invalid_tool_selection",
                    {
                        "agentic_tool": agentic_tool,
                        "model": model,
                        "claude_mode": claude_mode,
                    },
                ) from exc
            if str(exc) == "attachment_not_found":
                raise ThreadApiError(
                    400,
                    "attachment_not_found",
                    {"workspace_id": self.workspace_id},
                ) from exc
            raise
        latest_turn = await self.turn_repo.latest_turn(thread_id)
        latest_user = await self.message_repo.latest_user_message(thread_id)
        return await self._to_mutation(
            updated,
            latest_turn.id if latest_turn is not None else None,
            created_item_ids=[str(latest_user.id)] if latest_user is not None else [],
        )

    async def post_message(
        self,
        *,
        thread_id: str,
        user_id: str,
        message: dict,
    ) -> ThreadMutationResponse:
        self._require_runtime_action()
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})

        status_value = ThreadStatus(thread.status)
        if status_value == ThreadStatus.DRAFT:
            raise ThreadApiError(422, "use_submit_for_draft", {"thread_id": thread_id})

        resolved_model = await self._resolve_allowed_model(
            agentic_tool=thread.agentic_tool,
            requested_model=thread.model,
            claude_mode=thread.claude_mode,
        )

        try:
            queued_message = self._execution.prepare_message(thread_id, message)
        except ValueError as exc:
            self._raise_execution_error(exc, thread)
        queued_message = {"id": str(uuid4()), **queued_message}

        if status_value in RUNNING_STATUSES:
            updated = await self._try_queue_message(
                thread_id,
                queued_message,
                resolved_model=resolved_model,
            )
            if updated is not None:
                await self._emit_for_thread(updated, "messages_updated")
                return await self._to_mutation(
                    updated,
                    None,
                    use_fresh_session=False,
                )

        try:
            updated = await self._submit_with_resolved_model(
                thread=thread,
                original_model=thread.model,
                resolved_model=resolved_model,
                message=message,
            )
        except ValueError as exc:
            if str(exc) == "thread_busy":
                updated = await self._try_queue_message(
                    thread_id,
                    queued_message,
                    resolved_model=resolved_model,
                )
                if updated is not None:
                    await self._emit_for_thread(updated, "messages_updated")
                    return await self._to_mutation(
                        updated,
                        None,
                        use_fresh_session=False,
                    )
            self._raise_execution_error(exc, thread)
        latest_turn = await self.turn_repo.latest_turn(thread_id)
        latest_user = await self.message_repo.latest_user_message(thread_id)
        return await self._to_mutation(
            updated,
            latest_turn.id if latest_turn is not None else None,
            created_item_ids=[str(latest_user.id)] if latest_user is not None else [],
        )

    async def _submit_with_resolved_model(
        self,
        *,
        thread: ThreadModel,
        original_model: str,
        resolved_model: str,
        message: dict,
    ) -> ThreadModel:
        thread_id = thread.id
        if resolved_model == original_model:
            return await self._execution.submit(thread_id, message)

        thread.model = resolved_model
        await self.db.flush()
        try:
            return await self._execution.submit(thread_id, message)
        except BaseException:
            await self.thread_repo.locked_update(
                thread_id,
                lambda model: setattr(model, "model", original_model),
            )
            await self.db.commit()
            raise

    async def _try_queue_message(
        self,
        thread_id: str,
        queued_message: dict[str, Any],
        *,
        resolved_model: str | None = None,
    ) -> ThreadModel | None:
        queued = False

        def mutate(model: ThreadModel) -> None:
            nonlocal queued
            if ThreadStatus(model.status) not in RUNNING_STATUSES:
                return
            model.queued_messages = [*model.queued_messages, queued_message]
            if resolved_model is not None:
                model.model = resolved_model
            queued = True

        updated = await self.thread_repo.locked_update(thread_id, mutate)
        return updated if queued else None

    async def remove_queued_message(
        self,
        *,
        thread_id: str,
        user_id: str,
        queued_message_id: str,
    ) -> ThreadDetailResponse:
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})

        def mutate(model: ThreadModel) -> None:
            next_messages = [
                message
                for message in model.queued_messages
                if message.get("id") != queued_message_id
            ]
            if len(next_messages) == len(model.queued_messages):
                raise ThreadApiError(
                    404,
                    "queued_message_not_found",
                    {"queued_message_id": queued_message_id},
                )
            model.queued_messages = next_messages

        updated = await self.thread_repo.locked_update(thread_id, mutate)
        if updated is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        await self._emit_for_thread(updated, "messages_updated")
        return await self._to_detail(updated)

    async def answer_question(
        self,
        *,
        thread_id: str,
        user_id: str,
        message_id: int,
        answers: dict[str, str | list[str]],
        text: str,
    ) -> ThreadMutationResponse:
        self._require_runtime_action()
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})

        # Serialize concurrent answers: row lock is held until this request commits.
        locked = await self.thread_repo.locked_update(thread_id, lambda model: None)
        if locked is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})

        status_value = ThreadStatus(locked.status)
        if status_value == ThreadStatus.DRAFT:
            raise ThreadApiError(409, "invalid_state", {"thread_id": thread_id})
        if status_value in RUNNING_STATUSES:
            raise ThreadApiError(409, "thread_busy", {"thread_id": thread_id})
        question = await self.message_repo.get_for_thread(thread_id, message_id)
        if (
            question is None
            or question.type != "tool_call"
            or question.content.get("name") != QUESTION_TOOL_NAME
        ):
            raise ThreadApiError(404, "question_not_found", {"message_id": message_id})
        results = await self.message_repo.list_results_for_parent(thread_id, message_id)
        delivered = False
        already_answered = False
        for result_message in results:
            delivered = delivered or (
                result_message.result_kind == "provider_result"
                and not bool(result_message.content.get("isError", False))
            )
            already_answered = already_answered or (
                result_message.result_kind == "interaction_answer"
            )
        superseded = await self.message_repo.has_user_message_after(
            thread_id, question.message_sequence
        )

        if locked.queued_messages:
            raise ThreadApiError(
                409,
                QUESTION_EXPIRED_CODE,
                {
                    "message_id": message_id,
                    "reason": QUESTION_EXPIRED_QUEUED_MESSAGES,
                },
            )

        if not delivered or already_answered or superseded:
            reason = (
                QUESTION_EXPIRED_ALREADY_ANSWERED
                if already_answered
                else (
                    QUESTION_EXPIRED_SUPERSEDED
                    if superseded
                    else QUESTION_EXPIRED_NOT_DELIVERED
                )
            )
            raise ThreadApiError(
                409,
                QUESTION_EXPIRED_CODE,
                {"message_id": message_id, "reason": reason},
            )

        envelope, full_payload = self._execution._tool_result_envelope(
            {"answers": answers}, False
        )
        answer_message = await self.message_repo.append(
            thread_id,
            question.turn_id,
            question.turn_execution_id,
            "tool_result",
            envelope,
            source_event_key=f"question-answer:{message_id}",
            parent_tool_use_id=message_id,
            result_kind="interaction_answer",
        )
        if full_payload is not None:
            await self.message_repo.save_tool_result_content(
                message_id=answer_message.id,
                media_type=envelope["mediaType"],
                payload=full_payload,
                line_count=envelope["lineCount"],
            )

        try:
            restarted = await self._execution.restart(
                thread_id,
                prompt_text=text,
                attachments=[],
            )
        except ValueError as exc:
            self._raise_execution_error(exc, thread)
        await self._emit_for_thread(
            restarted,
            "timeline_updated",
            restarted.status,
            changed_item_ids=[str(question.id)],
        )
        return await self._to_mutation(
            restarted,
            question.turn_id,
            changed_item_ids=[str(question.id)],
        )

    async def cancel_thread(
        self, *, thread_id: str, user_id: str
    ) -> ThreadDetailResponse:
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})

        status_value = ThreadStatus(thread.status)
        if status_value not in RUNNING_STATUSES:
            raise ThreadApiError(409, "invalid_state", {"thread_id": thread_id})

        if self.event_session_factory is not None:
            return await self._cancel_thread_with_committed_state(
                thread=thread,
                status_value=status_value,
                user_id=user_id,
            )

        if status_value == ThreadStatus.QUEUED:
            if thread.active_turn_execution_id:
                await self._execution.stop(thread.active_turn_execution_id)

            def cancel_queued(model: ThreadModel) -> None:
                model.status = ThreadStatus.CANCELED.value
                model.queued_messages = []

            updated = await self.thread_repo.locked_update(
                thread_id,
                cancel_queued,
            )
            if updated is None:
                raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
            turn_id = await self._finish_canceled_turn(
                self.db, updated, thread.active_turn_execution_id
            )
            await self._emit_for_thread(
                updated,
                "timeline_updated",
                updated.status,
                turn_ids=[turn_id] if turn_id else [],
            )
            return await self._to_detail(updated)

        stopping = await self.thread_repo.locked_update(
            thread_id,
            lambda model: setattr(model, "status", ThreadStatus.STOPPING.value),
        )
        if stopping is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        await self._emit_for_thread(stopping, "status_updated", stopping.status)
        if stopping.active_turn_execution_id:
            await self._execution.stop(stopping.active_turn_execution_id)

        def cancel_stopped(model: ThreadModel) -> None:
            model.status = ThreadStatus.CANCELED.value
            model.queued_messages = []

        canceled = await self.thread_repo.locked_update(thread_id, cancel_stopped)
        if canceled is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        turn_id = await self._finish_canceled_turn(
            self.db, canceled, thread.active_turn_execution_id
        )
        await self._emit_for_thread(
            canceled,
            "timeline_updated",
            canceled.status,
            turn_ids=[turn_id] if turn_id else [],
        )
        return await self._to_detail(canceled)

    async def _cancel_thread_with_committed_state(
        self,
        *,
        thread: ThreadModel,
        status_value: ThreadStatus,
        user_id: str,
    ) -> ThreadDetailResponse:
        active_execution_id = thread.active_turn_execution_id
        if status_value == ThreadStatus.QUEUED:
            canceled = await self._commit_cancel_final_state(
                thread_id=thread.id,
                user_id=user_id,
                active_execution_id=active_execution_id,
            )
            self.db.expire_all()
            turn_id = await self._turn_id_for_execution(active_execution_id)
            await self._emit_for_thread(
                canceled,
                "timeline_updated",
                canceled.status,
                turn_ids=[turn_id] if turn_id else [],
            )
            if active_execution_id:
                await self._stop_runner_for_cancel(thread.id, active_execution_id)
            return await self._to_detail(canceled)

        stopping = await self._commit_stop_intent(
            thread_id=thread.id,
            user_id=user_id,
            active_execution_id=active_execution_id,
        )
        await self._emit_for_thread(stopping, "status_updated", stopping.status)
        try:
            if active_execution_id:
                await self._stop_runner_for_cancel(thread.id, active_execution_id)
        finally:
            canceled = await self._commit_cancel_final_state(
                thread_id=thread.id,
                user_id=user_id,
                active_execution_id=active_execution_id,
            )
            self.db.expire_all()
            turn_id = await self._turn_id_for_execution(active_execution_id)
            await self._emit_for_thread(
                canceled,
                "timeline_updated",
                canceled.status,
                turn_ids=[turn_id] if turn_id else [],
            )
        return await self._to_detail(canceled)

    async def _turn_id_for_execution(self, execution_id: str | None) -> str | None:
        if execution_id is None:
            return None
        execution = await self.turn_repo.get_execution(execution_id)
        return execution.turn_id if execution is not None else None

    async def _commit_stop_intent(
        self,
        *,
        thread_id: str,
        user_id: str,
        active_execution_id: str | None,
    ) -> ThreadModel:
        if self.event_session_factory is None:
            raise RuntimeError("event_session_factory_required")
        async with self.event_session_factory() as db:
            async with db.begin():
                repo = ThreadRepository(db, workspace_id=self.workspace_id)
                existing = await repo.get(thread_id, user_id=user_id)
                if existing is None:
                    raise ThreadApiError(
                        404, "thread_not_found", {"thread_id": thread_id}
                    )

                def mutate(model: ThreadModel) -> None:
                    if ThreadStatus(model.status) not in RUNNING_STATUSES:
                        raise ThreadApiError(
                            409,
                            "invalid_state",
                            {"thread_id": thread_id},
                        )
                    if model.active_turn_execution_id != active_execution_id:
                        raise ThreadApiError(
                            409,
                            "thread_busy",
                            {"thread_id": thread_id},
                        )
                    model.status = ThreadStatus.STOPPING.value

                updated = await repo.locked_update(thread_id, mutate)
                if updated is None:
                    raise ThreadApiError(
                        404, "thread_not_found", {"thread_id": thread_id}
                    )
                return updated

    async def _commit_cancel_final_state(
        self,
        *,
        thread_id: str,
        user_id: str,
        active_execution_id: str | None,
    ) -> ThreadModel:
        if self.event_session_factory is None:
            raise RuntimeError("event_session_factory_required")
        async with self.event_session_factory() as db:
            async with db.begin():
                repo = ThreadRepository(db, workspace_id=self.workspace_id)
                existing = await repo.get(thread_id, user_id=user_id)
                if existing is None:
                    raise ThreadApiError(
                        404, "thread_not_found", {"thread_id": thread_id}
                    )

                def mutate(model: ThreadModel) -> None:
                    status = ThreadStatus(model.status)
                    if status not in RUNNING_STATUSES:
                        if status != ThreadStatus.CANCELED:
                            raise ThreadApiError(
                                409,
                                "invalid_state",
                                {"thread_id": thread_id},
                            )
                    if (
                        model.active_turn_execution_id is not None
                        and model.active_turn_execution_id != active_execution_id
                    ):
                        raise ThreadApiError(
                            409,
                            "thread_busy",
                            {"thread_id": thread_id},
                        )
                    model.status = ThreadStatus.CANCELED.value
                    model.queued_messages = []

                updated = await repo.locked_update(thread_id, mutate)
                if updated is None:
                    raise ThreadApiError(
                        404, "thread_not_found", {"thread_id": thread_id}
                    )
                await self._finish_canceled_turn(db, updated, active_execution_id)
                return updated

    @staticmethod
    async def _finish_canceled_turn(
        db: AsyncSession,
        thread: ThreadModel,
        active_execution_id: str | None,
    ) -> str | None:
        if active_execution_id is None:
            thread.active_turn_id = None
            thread.active_turn_execution_id = None
            await db.flush()
            return None
        turn_repo = ThreadTurnRepository(db)
        execution = await turn_repo.get_execution(active_execution_id)
        if execution is None:
            thread.active_turn_id = None
            thread.active_turn_execution_id = None
            await db.flush()
            return None
        turn = await turn_repo.get_turn(thread.id, execution.turn_id)
        if turn is None:
            thread.active_turn_id = None
            thread.active_turn_execution_id = None
            await db.flush()
            return None
        await turn_repo.finish(
            thread=thread,
            execution=execution,
            turn=turn,
            status="canceled",
        )
        return turn.id

    async def _stop_runner_for_cancel(
        self,
        thread_id: str,
        active_execution_id: str,
    ) -> None:
        try:
            await self._execution.stop(active_execution_id)
        except Exception:
            logger.warning(
                "Agent runner stop failed during thread cancellation: thread_id=%s active_execution_id=%s",
                thread_id,
                active_execution_id,
                exc_info=True,
            )

    async def retry_thread(
        self, *, thread_id: str, user_id: str
    ) -> ThreadDetailResponse:
        self._require_runtime_action()
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        if thread.status != ThreadStatus.ERROR.value:
            raise ThreadApiError(409, "invalid_state", {"thread_id": thread_id})

        prompt_text, attachments = await self._last_user_message(thread_id)
        try:
            restarted = await self._execution.restart(
                thread_id,
                prompt_text=prompt_text,
                attachments=attachments,
            )
        except ValueError as exc:
            self._raise_execution_error(exc, thread)
        return await self._to_detail(restarted)

    async def archive_thread(
        self, thread_id: str, user_id: str
    ) -> ThreadDetailResponse:
        self._require_runtime_action()
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})

        def mutate(model: ThreadModel) -> None:
            model.archived = True

        updated = await self.thread_repo.locked_update(thread_id, mutate)
        if updated is None:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        await self._execution.destroy_thread(thread_id)
        await self._emit_for_thread(updated, "archived")
        return await self._to_detail(updated)

    async def delete_thread(self, thread_id: str, user_id: str) -> None:
        self._require_runtime_action()
        thread = await self.thread_repo.get(thread_id, user_id=user_id)
        if thread is None or thread.origin != "user":
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})

        result = await self.thread_repo.delete(thread_id, user_id=user_id)
        if result == ThreadDeleteResult.NOT_FOUND:
            raise ThreadApiError(404, "thread_not_found", {"thread_id": thread_id})
        if result == ThreadDeleteResult.RUNNING:
            raise ThreadApiError(409, "thread_running", {"thread_id": thread_id})

        await self._execution.destroy_thread(thread_id)
        await self._emit_for_thread(thread, "deleted")

    def _require_runtime_action(self) -> None:
        try:
            get_runtime_admission_state().require_accepting()
        except RuntimeDrainingError as exc:
            raise ThreadApiError(
                status_code=423,
                error_code=exc.error_code,
                error_info={},
            ) from exc

    def _raise_execution_error(self, exc: ValueError, thread: ThreadModel) -> Never:
        if str(exc) == "capabilities_unavailable":
            raise ThreadApiError(
                409,
                "capabilities_unavailable",
                {"workspace_id": self.workspace_id},
            ) from exc
        if str(exc) == "invalid_tool_selection":
            raise ThreadApiError(
                409,
                "invalid_tool_selection",
                {
                    "agentic_tool": thread.agentic_tool,
                    "model": thread.model,
                    "claude_mode": thread.claude_mode,
                },
            ) from exc
        if str(exc) == "attachment_not_found":
            raise ThreadApiError(
                400,
                "attachment_not_found",
                {"workspace_id": self.workspace_id},
            ) from exc
        if str(exc) == "thread_busy":
            raise ThreadApiError(409, "thread_busy", {"thread_id": thread.id}) from exc
        raise exc

    async def _resolve_allowed_model(
        self,
        *,
        agentic_tool: str,
        requested_model: str,
        claude_mode: str | None,
    ) -> str:
        capabilities = await self.capabilities_store.get(self.db, self.workspace_id)
        if capabilities is None:
            raise ThreadApiError(
                status_code=409,
                error_code="capabilities_unavailable",
                error_info={"workspace_id": self.workspace_id},
            )
        capability = next(
            (tool for tool in capabilities.tools if tool.id == agentic_tool),
            None,
        )
        if capability is None:
            return requested_model
        if capabilities.validate_selection(agentic_tool, requested_model, claude_mode):
            return requested_model
        return capability.default_model

    async def _last_user_message(
        self, thread_id: str
    ) -> tuple[str, list[dict[str, Any]]]:
        message = await self.message_repo.latest_user_message(thread_id)
        if message is not None:
            parts = message.content.get("parts", [])
            text = "\n".join(
                str(part.get("text") or "")
                for part in parts
                if isinstance(part, dict) and part.get("type") == "text"
            )
            attachments = [
                dict(part)
                for part in parts
                if isinstance(part, dict)
                and part.get("type") in {"image", "pdf", "text-file", "file"}
            ]
            return text, attachments
        return "", []

    async def _reconcile_stale_running_thread(self, thread: ThreadModel) -> ThreadModel:
        if ThreadStatus(thread.status) not in RUNTIME_RESTART_RECONCILIATION_STATUSES:
            return thread

        active_execution_id = thread.active_turn_execution_id
        if active_execution_id is not None and self._execution.is_alive(
            active_execution_id
        ):
            return thread

        def mutate(model: ThreadModel) -> None:
            if (
                ThreadStatus(model.status)
                not in RUNTIME_RESTART_RECONCILIATION_STATUSES
            ):
                return
            if model.active_turn_execution_id != active_execution_id:
                return
            apply_thread_error(
                model,
                error_code="runtime_restarted",
                error_message=None,
                error_info={"active_execution_id": active_execution_id},
                preserve_existing_specific=False,
            )

        updated = await self.thread_repo.locked_update(thread.id, mutate)
        if updated is None:
            return thread
        if updated.status == ThreadStatus.ERROR.value:
            await self._emit_for_thread(updated, "status_updated", updated.status)
        return updated

    async def _emit_for_thread(
        self,
        thread: ThreadModel,
        type_: str,
        status: str | None = None,
        *,
        turn_ids: list[str] | None = None,
        created_item_ids: list[str] | None = None,
        changed_item_ids: list[str] | None = None,
    ) -> None:
        user_id = None if thread.origin == "automation" else thread.user_id
        turns = []
        executions = []
        if type_ == "timeline_updated" and turn_ids:
            turn_models = await self.turn_repo.list_turns_by_ids(
                thread.id, set(turn_ids)
            )
            turns = [
                {"id": item.id, "version": item.version, "status": item.status}
                for item in turn_models
            ]
            for turn in turn_models:
                for execution in await self.turn_repo.list_executions(turn.id):
                    executions.append(
                        {
                            "id": execution.id,
                            "version": execution.version,
                            "turnId": execution.turn_id,
                            "status": execution.status,
                        }
                    )
        await self.invalidation_sink.emit(
            user_id,
            thread.workspace_id,
            thread.id,
            type_,
            status=status,
            thread_version=thread.version,
            created_item_ids=created_item_ids,
            changed_item_ids=changed_item_ids,
            turns=turns,
            executions=executions,
        )

    @staticmethod
    def _to_summary(thread: ThreadModel) -> ThreadSummaryResponse:
        return ThreadSummaryResponse(
            id=thread.id,
            workspaceId=thread.workspace_id,
            userId=thread.user_id,
            origin=thread.origin,
            automationJobId=thread.automation_job_id,
            automationExecutionId=thread.automation_execution_id,
            title=thread.title or UNTITLED_THREAD_TITLE_KEY,
            agenticTool=thread.agentic_tool,
            model=thread.model,
            claudeMode=thread.claude_mode,
            status=thread.status,
            version=thread.version,
            activeTurnId=thread.active_turn_id,
            activeTurnExecutionId=thread.active_turn_execution_id,
            gitContextId=thread.git_context_id,
            contextTokens=thread.context_tokens,
            contextWindow=thread.context_window,
            archived=thread.archived,
            errorCode=thread.error_code,
            errorInfo=thread.error_info,
            errorMessage=thread.error_message,
            createdAt=thread.created_at,
            updatedAt=thread.updated_at,
        )

    async def _to_detail(self, thread: ThreadModel) -> ThreadDetailResponse:
        return self._detail_response(thread)

    @staticmethod
    def _to_turn_metadata(turn: ThreadTurnModel) -> ThreadTurnMetadataResponse:
        return ThreadTurnMetadataResponse(
            id=turn.id,
            sequence=turn.sequence,
            version=turn.version,
            status=turn.status,
            errorCode=turn.error_code,
            errorInfo=turn.error_info,
            createdAt=turn.created_at,
            completedAt=turn.completed_at,
        )

    @staticmethod
    def _to_execution_metadata(
        execution: ThreadTurnExecutionModel,
    ) -> ThreadExecutionMetadataResponse:
        return ThreadExecutionMetadataResponse(
            id=execution.id,
            sequence=execution.sequence,
            agenticTool=execution.agentic_tool,
            agentResumeId=execution.agent_resume_id,
            version=execution.version,
            status=execution.status,
            errorCode=execution.error_code,
            errorInfo=execution.error_info,
            createdAt=execution.created_at,
            completedAt=execution.completed_at,
        )

    async def _project_timeline(
        self, thread_id: str, anchors: list[ThreadMessageModel]
    ) -> TimelineItemsResponse:
        tool_ids = [message.id for message in anchors if message.type == "tool_call"]
        results = await self.message_repo.list_results_for_parents(thread_id, tool_ids)
        results_by_parent: dict[int, dict[str, ThreadMessageModel]] = {}
        for result in results:
            if result.parent_tool_use_id is None or result.result_kind is None:
                continue
            results_by_parent.setdefault(result.parent_tool_use_id, {})[
                result.result_kind
            ] = result

        turns = await self.turn_repo.list_turns_by_ids(
            thread_id, {message.turn_id for message in anchors}
        )
        executions = await self.turn_repo.list_executions_by_ids(
            {message.turn_execution_id for message in anchors}
        )
        items = [
            self._to_timeline_item(message, results_by_parent.get(message.id, {}))
            for message in anchors
        ]
        return TimelineItemsResponse(
            items=items,
            turns=[self._to_turn_metadata(turn) for turn in turns],
            executions=[
                self._to_execution_metadata(execution) for execution in executions
            ],
        )

    @staticmethod
    def _to_timeline_item(
        message: ThreadMessageModel,
        results: dict[str, ThreadMessageModel],
    ) -> TimelineMessageItemResponse:
        if message.type != "tool_call":
            return TimelineMessageItemResponse(
                id=str(message.id),
                sequence=message.message_sequence,
                itemVersion=message.message_sequence,
                turnId=message.turn_id,
                turnExecutionId=message.turn_execution_id,
                type=message.type,
                parentItemId=(
                    str(message.parent_tool_use_id)
                    if message.parent_tool_use_id is not None
                    else None
                ),
                content=message.content,
                providerResult=None,
                interactionAnswer=None,
                createdAt=message.created_at,
            )

        provider = results.get("provider_result")
        answer = results.get("interaction_answer")
        provider_response = None
        if provider is not None:
            provider_response = TimelineToolResultResponse(
                messageId=str(provider.id),
                isError=bool(provider.content.get("isError", False)),
                preview=str(provider.content.get("preview") or ""),
                byteLength=int(provider.content.get("byteLength") or 0),
                lineCount=provider.content.get("lineCount"),
                truncated=bool(provider.content.get("truncated", False)),
                mediaType=str(provider.content.get("mediaType") or "text/plain"),
            )
        answer_response = None
        if answer is not None:
            answers: dict[str, str | list[str]] = {}
            preview = answer.content.get("preview")
            if isinstance(preview, str):
                try:
                    decoded = json.loads(preview)
                except ValueError:
                    decoded = None
                if isinstance(decoded, dict) and isinstance(
                    decoded.get("answers"), dict
                ):
                    answers = decoded["answers"]
            answer_response = TimelineInteractionAnswerResponse(
                messageId=str(answer.id), answers=answers
            )
        item_version = max(
            [message.message_sequence]
            + [result.message_sequence for result in results.values()]
        )
        raw_parameters = message.content.get("parameters")
        parameters: dict[str, Any] = (
            raw_parameters if isinstance(raw_parameters, dict) else {}
        )
        return TimelineMessageItemResponse(
            id=str(message.id),
            sequence=message.message_sequence,
            itemVersion=item_version,
            turnId=message.turn_id,
            turnExecutionId=message.turn_execution_id,
            type="tool",
            parentItemId=(
                str(message.parent_tool_use_id)
                if message.parent_tool_use_id is not None
                else None
            ),
            call=TimelineToolCallResponse(
                name=str(message.content.get("name") or "unknown"),
                parameters=parameters,
            ),
            providerResult=provider_response,
            interactionAnswer=answer_response,
            createdAt=message.created_at,
        )

    async def _to_mutation(
        self,
        thread: ThreadModel,
        metadata_turn_id: str | None,
        *,
        use_fresh_session: bool = True,
        created_item_ids: list[str] | None = None,
        changed_item_ids: list[str] | None = None,
    ) -> ThreadMutationResponse:
        if use_fresh_session and self.event_session_factory is not None:
            async with self.event_session_factory() as db:
                fresh_thread = await db.get(ThreadModel, thread.id)
                if (
                    fresh_thread is None
                    or fresh_thread.workspace_id != self.workspace_id
                ):
                    raise ThreadApiError(
                        404,
                        "thread_not_found",
                        {"thread_id": thread.id},
                    )
                turn_repo = ThreadTurnRepository(db)
                turns: list[ThreadTurnMetadataResponse] = []
                executions: list[ThreadExecutionMetadataResponse] = []
                if metadata_turn_id is not None:
                    turn = await turn_repo.get_turn(fresh_thread.id, metadata_turn_id)
                    if turn is not None:
                        turns = [self._to_turn_metadata(turn)]
                        executions = [
                            self._to_execution_metadata(execution)
                            for execution in await turn_repo.list_executions(turn.id)
                        ]
                detail = self._detail_response(fresh_thread)
                return ThreadMutationResponse(
                    **detail.model_dump(),
                    createdItemIds=created_item_ids or [],
                    changedItemIds=changed_item_ids or [],
                    turns=turns,
                    executions=executions,
                )

        turns = []
        executions = []
        if metadata_turn_id is not None:
            turn = await self.turn_repo.get_turn(thread.id, metadata_turn_id)
            if turn is not None:
                turns = [self._to_turn_metadata(turn)]
                executions = [
                    self._to_execution_metadata(execution)
                    for execution in await self.turn_repo.list_executions(turn.id)
                ]
        detail = self._detail_response(thread)
        return ThreadMutationResponse(
            **detail.model_dump(),
            createdItemIds=created_item_ids or [],
            changedItemIds=changed_item_ids or [],
            turns=turns,
            executions=executions,
        )

    def _detail_response(
        self,
        thread: ThreadModel,
    ) -> ThreadDetailResponse:
        return ThreadDetailResponse(
            **self._to_summary(thread).model_dump(),
            queuedMessages=thread.queued_messages,
            draftMessage=thread.draft_message,
        )
