"""Codex tool implementation backed by the Python app-server SDK."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode
from uuid import uuid4

from codex_app_server.generated.v2_all import CommandExecutionStatus, PatchApplyStatus
from codex_app_server import TextInput

from app.database import async_session_scope
from app.modules.agent_session.codex_usage import codex_context_usage
from app.modules.agent_session.domain.enums import PermissionMode
from app.modules.agent_session.domain.value_objects import CodexPermissionConfig
from app.modules.agent_session.repositories.agent_session_repository import (
    AgentSessionRepository,
)
from app.modules.agent_session.repositories.message_repository import MessageRepository
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.tool_decision_manager import (
    global_tool_decision_manager,
)
from app.modules.agent_session.services.tools.base.message_builder import (
    _build_message_dict,
    create_assistant_message,
    create_tool_result_message,
    create_user_message,
)
from app.modules.agent_session.services.tools.base.streaming_callbacks import (
    StreamingCallbacks,
)
from app.modules.agent_session.services.tools.base.tool_interface import ITool
from app.modules.agent_session.services.tools.base.types import TaskResult, ToolExecutionError

from .approval_handler import CodexApprovalHandler
from .client_manager import (
    CodexAuthenticationRequiredError,
    CodexClientManager,
    get_codex_client_manager,
)
from .notification_mapper import (
    CommandOutputDelta,
    CommandToolEnd,
    CommandToolStart,
    ContextCompactionEnd,
    FileChangeEnd,
    FileChangeOutputDelta,
    FileChangePatchUpdated,
    FileChangeStart,
    ImageGenerationEnd,
    IgnoredEvent,
    PlanDelta,
    StreamError,
    TextDelta,
    TextFinal,
    ThinkingDelta,
    ThinkingEnd,
    ThinkingPart,
    TokenUsageEvent,
    NotificationMapper,
)
from .permission_mapper import to_thread_start_kwargs, to_turn_kwargs

logger = logging.getLogger(__name__)

_RECONNECT_MESSAGE_RE = re.compile(r"Reconnecting\.\.\.\s*(\d+)/(\d+)")
_WORKSPACE_ROOT = Path("/workspace")
_CODEX_GENERATED_IMAGE_DIR = _WORKSPACE_ROOT / ".aileron" / "generated-images" / "codex"


class CodexExecutionError(ToolExecutionError):
    """Codex execution failed."""

    error_code = "CODEX_EXECUTION_FAILED"
    message_key = "workspace.chat.errors.codexExecutionFailed"


class CodexAuthenticationError(ToolExecutionError):
    """Codex authentication is required."""

    error_code = "CODEX_AUTHENTICATION_FAILED"
    message_key = "workspace.chat.errors.codexAuthenticationFailed"


class CodexTool(ITool):
    """ITool implementation for Codex SDK execution."""

    def __init__(
        self,
        client_manager: CodexClientManager | None = None,
        message_service_factory=MessageService,
    ) -> None:
        self._manager = client_manager or get_codex_client_manager()
        self._message_service_factory = message_service_factory

    async def execute_task(
        self,
        session_id: str,
        prompt: str,
        task_id: Optional[str] = None,
        permission_mode: Optional[PermissionMode] = None,
        streaming_callbacks: Optional[StreamingCallbacks] = None,
    ) -> TaskResult:
        session, cfg, cwd = await self._load_session_context(session_id)

        try:
            state = await self._manager.get_or_create(
                session_id=session_id,
                cwd=cwd,
                sdk_session_id=session.sdk_session_id,
                permission_config=cfg,
            )
        except CodexAuthenticationRequiredError as exc:
            raise CodexAuthenticationError() from exc
        if state.active_turn is not None:
            raise CodexExecutionError()

        emit_event = (
            streaming_callbacks.emit_event
            if streaming_callbacks and hasattr(streaming_callbacks, "emit_event")
            else self._noop_emit_event
        )
        loop = asyncio.get_running_loop()
        handler = CodexApprovalHandler(
            session_id=session_id,
            task_id=task_id or "",
            emit_event=emit_event,
            loop=loop,
        )

        text_message_ids: dict[str, str] = {}
        command_output_buffers: dict[str, list[str]] = {}
        file_patch_snapshots: dict[str, list[Any]] = {}
        thinking_message_ids: dict[str, str] = {}
        open_thinking_ids: set[str] = set()
        assistant_message_ids: list[str] = []
        token_usage: dict[str, Any] | None = None
        raw_events: dict[str, Any] = {}
        mapper = NotificationMapper()

        user_message = await self._persist_user_message(session_id, prompt, task_id)
        if streaming_callbacks:
            await streaming_callbacks.on_message_created(user_message)

        state.dispatcher.set_current(handler)
        global_tool_decision_manager.register_hooks(session_id, handler)

        try:
            state, handle = await self._start_turn_with_broken_pipe_recovery(
                session_id=session_id,
                session=session,
                cfg=cfg,
                cwd=cwd,
                prompt=prompt,
                state=state,
            )
            state.active_turn = handle

            async for notification in handle.stream():
                event = mapper.dispatch(notification.method, notification.payload)

                if isinstance(event, TextDelta):
                    message_id = await self._ensure_text_message(
                        session_id,
                        task_id,
                        event.item_id,
                        text_message_ids,
                        assistant_message_ids,
                        streaming_callbacks,
                    )
                    if streaming_callbacks:
                        await streaming_callbacks.on_stream_chunk(message_id, event.delta)

                elif isinstance(event, TextFinal):
                    if not event.text and event.item_id not in text_message_ids:
                        continue
                    await self._finalize_text_message(
                        session_id,
                        task_id,
                        event,
                        text_message_ids,
                        assistant_message_ids,
                        streaming_callbacks,
                    )

                elif isinstance(event, ImageGenerationEnd):
                    message = await self._persist_image_generation_message(
                        session_id=session_id,
                        task_id=task_id,
                        event=event,
                    )
                    if message:
                        assistant_message_ids.append(message["message_id"])
                        raw_events.setdefault("generated_images", []).append(
                            {
                                "item_id": event.item_id,
                                "status": event.status,
                                "saved_path": event.saved_path,
                                "revised_prompt": event.revised_prompt,
                            }
                        )
                        if streaming_callbacks:
                            await streaming_callbacks.on_message_created(message)

                elif isinstance(event, CommandToolStart):
                    command_output_buffers[event.item_id] = []
                    message = await self._persist_tool_use_message(
                        session_id=session_id,
                        task_id=task_id,
                        tool_use_id=event.item_id,
                        name="shell",
                        tool_input={"command": event.command, "cwd": event.cwd},
                    )
                    assistant_message_ids.append(message["message_id"])
                    if streaming_callbacks:
                        await streaming_callbacks.on_message_created(message)

                elif isinstance(event, CommandOutputDelta):
                    command_output_buffers.setdefault(event.item_id, []).append(event.delta)

                elif isinstance(event, CommandToolEnd):
                    content = event.aggregated_output or "".join(
                        command_output_buffers.get(event.item_id, [])
                    )
                    message = await self._persist_tool_result_message(
                        session_id=session_id,
                        task_id=task_id,
                        tool_use_id=event.item_id,
                        content=content,
                        is_error=event.status != CommandExecutionStatus.completed,
                    )
                    if streaming_callbacks:
                        await streaming_callbacks.on_message_created(message)

                elif isinstance(event, FileChangeStart):
                    file_patch_snapshots[event.item_id] = event.changes
                    message = await self._persist_file_change_use_message(
                        session_id=session_id,
                        task_id=task_id,
                        item_id=event.item_id,
                        changes=event.changes,
                    )
                    assistant_message_ids.append(message["message_id"])
                    if streaming_callbacks:
                        await streaming_callbacks.on_message_created(message)

                elif isinstance(event, FileChangeOutputDelta):
                    raw_events.setdefault("file_output", {}).setdefault(
                        event.item_id,
                        [],
                    ).append(event.delta)

                elif isinstance(event, FileChangePatchUpdated):
                    file_patch_snapshots[event.item_id] = event.changes

                elif isinstance(event, FileChangeEnd):
                    changes = event.changes or file_patch_snapshots.get(event.item_id, [])
                    message = await self._persist_file_change_result_message(
                        session_id=session_id,
                        task_id=task_id,
                        item_id=event.item_id,
                        changes=changes,
                        status=event.status,
                    )
                    if streaming_callbacks:
                        await streaming_callbacks.on_message_created(message)

                elif isinstance(event, ThinkingDelta):
                    message_id = thinking_message_ids.setdefault(
                        event.item_id,
                        f"codex-thinking:{event.item_id}",
                    )
                    if streaming_callbacks and message_id not in open_thinking_ids:
                        open_thinking_ids.add(message_id)
                        await streaming_callbacks.on_thinking_start(message_id)
                    if streaming_callbacks:
                        await streaming_callbacks.on_thinking_chunk(message_id, event.delta)

                elif isinstance(event, ThinkingPart):
                    raw_events.setdefault("thinking_parts", {})[event.item_id] = event.text

                elif isinstance(event, ThinkingEnd):
                    await self._close_thinking(
                        event.item_id,
                        thinking_message_ids,
                        open_thinking_ids,
                        streaming_callbacks,
                    )

                elif isinstance(event, PlanDelta):
                    raw_events["plan"] = event.delta

                elif isinstance(event, TokenUsageEvent):
                    token_usage = event.token_usage

                elif isinstance(event, ContextCompactionEnd):
                    raw_events.setdefault("context_compactions", []).append(
                        {"item_id": event.item_id}
                    )

                elif isinstance(event, StreamError):
                    if event.will_retry:
                        logger.warning(
                            "Codex stream retrying after error: %s", event.message
                        )
                        if streaming_callbacks and hasattr(
                            streaming_callbacks, "on_status_notice"
                        ):
                            await streaming_callbacks.on_status_notice(
                                self._stream_retry_notice(event.message)
                            )
                        continue
                    logger.error("Codex stream error: %s", event.message)
                    raise CodexExecutionError()

                elif isinstance(event, IgnoredEvent):
                    continue

            await self._close_all_thinking(
                thinking_message_ids,
                open_thinking_ids,
                streaming_callbacks,
            )

        finally:
            state.dispatcher.set_current(None)
            state.active_turn = None
            global_tool_decision_manager.unregister_hooks(session_id)

        raw_sdk_response = {
            "type": "codex",
            "token_usage": token_usage,
            **raw_events,
        }
        context_window = self._context_window(token_usage)
        context_window_limit = self._context_window_limit(token_usage)

        return TaskResult(
            user_message_id=user_message["message_id"],
            assistant_message_ids=assistant_message_ids,
            raw_sdk_response=raw_sdk_response,
            context_window=context_window,
            context_window_limit=context_window_limit,
        )

    async def stop_task(
        self,
        session_id: str,
        task_id: Optional[str] = None,
    ) -> dict:
        state = await self._manager.get_state(session_id)
        if state and state.active_turn:
            try:
                await state.active_turn.interrupt()
            except Exception as exc:
                logger.warning("Codex turn interrupt failed session=%s: %s", session_id[:8], exc)
        return {"status": "stopped"}

    async def _start_turn_with_broken_pipe_recovery(
        self,
        *,
        session_id: str,
        session: Any,
        cfg: CodexPermissionConfig | None,
        cwd: str,
        prompt: str,
        state: Any,
    ) -> tuple[Any, Any]:
        pipe_exc: BrokenPipeError | None = None
        try:
            handle = await self._start_turn(
                session_id=session_id,
                cfg=cfg,
                cwd=cwd,
                prompt=prompt,
                state=state,
            )
            return state, handle
        except BrokenPipeError as exc:
            pipe_exc = exc
            logger.warning(
                "Codex app-server pipe broke; rebuilding session=%s",
                session_id[:8],
            )
            state.dispatcher.set_current(None)
            state.active_turn = None
            await self._manager.close_session(session_id)

        try:
            recovered_state = await self._manager.get_or_create(
                session_id=session_id,
                cwd=cwd,
                sdk_session_id=session.sdk_session_id,
                permission_config=cfg,
            )
        except CodexAuthenticationRequiredError as auth_exc:
            raise CodexAuthenticationError() from auth_exc
        if recovered_state.active_turn is not None:
            raise CodexExecutionError() from pipe_exc

        try:
            handle = await self._start_turn(
                session_id=session_id,
                cfg=cfg,
                cwd=cwd,
                prompt=prompt,
                state=recovered_state,
            )
        except BrokenPipeError as retry_exc:
            raise CodexExecutionError() from retry_exc
        return recovered_state, handle

    async def _start_turn(
        self,
        *,
        session_id: str,
        cfg: CodexPermissionConfig | None,
        cwd: str,
        prompt: str,
        state: Any,
    ) -> Any:
        if state.thread is None:
            state.thread = await state.codex.thread_start(
                **to_thread_start_kwargs(cfg, cwd)
            )
            await self._save_sdk_session_id(session_id, state.thread.id)

        return await state.thread.turn([TextInput(prompt)], **to_turn_kwargs(cfg, cwd))

    @staticmethod
    def _stream_retry_notice(message: str) -> dict[str, Any]:
        reconnect_match = _RECONNECT_MESSAGE_RE.search(message)
        if reconnect_match:
            attempt, max_attempts = reconnect_match.groups()
            return {
                "message_key": "workspace.chat.status.codexReconnecting",
                "severity": "warning",
                "params": {
                    "attempt": int(attempt),
                    "max_attempts": int(max_attempts),
                },
            }
        return {
            "message_key": "workspace.chat.status.codexRetrying",
            "severity": "warning",
        }

    async def _load_session_context(
        self,
        session_id: str,
    ) -> tuple[Any, CodexPermissionConfig | None, str]:
        async with async_session_scope() as db:
            repo = AgentSessionRepository(db)
            model = await repo.find_by_id(session_id)
            if not model:
                raise CodexExecutionError()
            session = repo.to_entity(model)
        cfg = session.permission_config.codex if session.permission_config else None
        cwd = session.custom_context.get("workspace_path") or "/workspace"
        return session, cfg, cwd

    async def _persist_user_message(
        self,
        session_id: str,
        prompt: str,
        task_id: str | None,
    ) -> dict[str, Any]:
        async with async_session_scope() as db:
            service = self._message_service_factory(db)
            return await create_user_message(
                session_id=session_id,
                prompt=prompt,
                task_id=task_id,
                index=0,
                message_service=service,
                source="codex-sdk",
            )

    async def _save_sdk_session_id(self, session_id: str, thread_id: str) -> None:
        async with async_session_scope() as db:
            repo = AgentSessionRepository(db)
            await repo.set_sdk_session_id(session_id, thread_id)

    async def _ensure_text_message(
        self,
        session_id: str,
        task_id: str | None,
        item_id: str,
        text_message_ids: dict[str, str],
        assistant_message_ids: list[str],
        streaming_callbacks: StreamingCallbacks | None,
    ) -> str:
        existing = text_message_ids.get(item_id)
        if existing:
            return existing

        async with async_session_scope() as db:
            service = MessageService(db)
            message = await create_assistant_message(
                session_id=session_id,
                content=[{"type": "text", "text": ""}],
                task_id=task_id,
                index=0,
                message_service=service,
                source="codex-sdk",
            )
        message_id = message["message_id"]
        text_message_ids[item_id] = message_id
        assistant_message_ids.append(message_id)
        if streaming_callbacks:
            await streaming_callbacks.on_stream_start(message_id)
        return message_id

    async def _finalize_text_message(
        self,
        session_id: str,
        task_id: str | None,
        event: TextFinal,
        text_message_ids: dict[str, str],
        assistant_message_ids: list[str],
        streaming_callbacks: StreamingCallbacks | None,
    ) -> None:
        message_id = text_message_ids.get(event.item_id)
        if not message_id:
            async with async_session_scope() as db:
                service = self._message_service_factory(db)
                message = await create_assistant_message(
                    session_id=session_id,
                    content=[{"type": "text", "text": event.text}],
                    task_id=task_id,
                    index=0,
                    message_service=service,
                    source="codex-sdk",
                )
            assistant_message_ids.append(message["message_id"])
            if streaming_callbacks:
                await streaming_callbacks.on_message_created(message)
            return

        message = await self._update_message_content(
            message_id,
            [{"type": "text", "text": event.text}],
        )
        if streaming_callbacks:
            await streaming_callbacks.on_stream_end(message_id)
            if message:
                await streaming_callbacks.on_message_created(message)

    async def _update_message_content(
        self,
        message_id: str,
        content: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        async with async_session_scope() as db:
            repo = MessageRepository(db)
            model = await repo.find_by_id(message_id)
            if not model:
                return None
            try:
                data = json.loads(model.data) if model.data else {}
            except (TypeError, json.JSONDecodeError):
                data = {}
            data["content"] = content
            updated = await repo.update(
                message_id,
                {"data": json.dumps(data, ensure_ascii=False)},
            )
            if not updated:
                return None
            return _build_message_dict(repo.to_entity(updated))

    async def _persist_tool_use_message(
        self,
        session_id: str,
        task_id: str | None,
        tool_use_id: str,
        name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._persist_assistant_blocks(
            session_id,
            task_id,
            [{"type": "tool_use", "id": tool_use_id, "name": name, "input": tool_input}],
        )

    async def _persist_file_change_use_message(
        self,
        session_id: str,
        task_id: str | None,
        item_id: str,
        changes: list[Any],
    ) -> dict[str, Any]:
        blocks = [
            {
                "type": "tool_use",
                "id": f"{item_id}:{idx}",
                "name": "write_file",
                "input": {"path": change.path},
            }
            for idx, change in enumerate(changes)
        ]
        return await self._persist_assistant_blocks(session_id, task_id, blocks)

    async def _persist_assistant_blocks(
        self,
        session_id: str,
        task_id: str | None,
        blocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        async with async_session_scope() as db:
            service = self._message_service_factory(db)
            return await create_assistant_message(
                session_id=session_id,
                content=blocks,
                task_id=task_id,
                index=0,
                message_service=service,
                source="codex-sdk",
                tool_uses=[
                    {"id": b["id"], "name": b["name"], "input": b["input"]}
                    for b in blocks
                    if b.get("type") == "tool_use"
                ],
            )

    async def _persist_image_generation_message(
        self,
        session_id: str,
        task_id: str | None,
        event: ImageGenerationEnd,
    ) -> dict[str, Any] | None:
        source = self._image_source_from_generation(event)
        if not source:
            logger.warning(
                "Codex image generation completed without readable image item_id=%s status=%s",
                event.item_id,
                event.status,
            )
            return None

        return await self._persist_assistant_blocks(
            session_id,
            task_id,
            [{"type": "image", "source": source}],
        )

    @classmethod
    def _image_source_from_generation(cls, event: ImageGenerationEnd) -> dict[str, Any] | None:
        media_type = "image/png"
        if event.saved_path:
            path = Path(event.saved_path)
            if path.exists() and path.is_file():
                guessed_type = mimetypes.guess_type(path.name)[0]
                media_type = guessed_type or media_type
                workspace_path = cls._ensure_workspace_image_file(
                    event=event,
                    image_bytes=path.read_bytes(),
                    media_type=media_type,
                    source_path=path,
                )
                return cls._image_url_source(workspace_path, media_type)

        if event.result:
            result = event.result
            if result.startswith("data:") and ";base64," in result:
                header, data = result.split(";base64,", 1)
                media_type = header.removeprefix("data:") or media_type
                result = data
            try:
                image_bytes = base64.b64decode(result, validate=True)
            except (binascii.Error, ValueError):
                logger.warning(
                    "Codex image generation result was not valid base64 item_id=%s status=%s",
                    event.item_id,
                    event.status,
                )
                return None
            workspace_path = cls._ensure_workspace_image_file(
                event=event,
                image_bytes=image_bytes,
                media_type=media_type,
                source_path=None,
            )
            return cls._image_url_source(workspace_path, media_type)

        return None

    @staticmethod
    def _image_url_source(path: Path, media_type: str) -> dict[str, Any]:
        file_path = str(path)
        request_path = CodexTool._workspace_file_request_path(path)
        return {
            "type": "url",
            "media_type": media_type,
            "url": f"/api/v1/files/content?{urlencode({'path': request_path, 'raw': 'true'})}",
            "path": file_path,
        }

    @staticmethod
    def _workspace_file_request_path(path: Path) -> str:
        try:
            relative_path = path.resolve(strict=False).relative_to(
                _WORKSPACE_ROOT.resolve(strict=False)
            )
            return f"/{relative_path.as_posix()}"
        except ValueError:
            return str(path)

    @classmethod
    def _ensure_workspace_image_file(
        cls,
        *,
        event: ImageGenerationEnd,
        image_bytes: bytes,
        media_type: str,
        source_path: Path | None,
    ) -> Path:
        if source_path and cls._is_under_workspace(source_path):
            return source_path

        _CODEX_GENERATED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        suffix = (
            source_path.suffix
            if source_path and source_path.suffix
            else mimetypes.guess_extension(media_type) or ".png"
        )
        safe_item_id = (
            re.sub(r"[^A-Za-z0-9_.-]+", "-", event.item_id).strip(".-") or "image"
        )
        target = _CODEX_GENERATED_IMAGE_DIR / f"{safe_item_id}-{uuid4().hex}{suffix}"
        target.write_bytes(image_bytes)
        return target

    @staticmethod
    def _is_under_workspace(path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(_WORKSPACE_ROOT.resolve(strict=False))
            return True
        except ValueError:
            return False

    async def _persist_tool_result_message(
        self,
        session_id: str,
        task_id: str | None,
        tool_use_id: str,
        content: Any,
        is_error: bool,
    ) -> dict[str, Any]:
        async with async_session_scope() as db:
            service = self._message_service_factory(db)
            return await create_tool_result_message(
                session_id=session_id,
                content=[
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": content,
                        "is_error": is_error,
                    }
                ],
                task_id=task_id,
                index=0,
                message_service=service,
                source="codex-sdk",
            )

    async def _persist_file_change_result_message(
        self,
        session_id: str,
        task_id: str | None,
        item_id: str,
        changes: list[Any],
        status: PatchApplyStatus,
    ) -> dict[str, Any]:
        blocks = [
            {
                "type": "tool_result",
                "tool_use_id": f"{item_id}:{idx}",
                "is_error": status != PatchApplyStatus.completed,
                "content": {
                    "content": [
                        {
                            "type": "diff",
                            "path": change.path,
                            "newText": change.diff,
                        }
                    ],
                    "status": status.value,
                },
            }
            for idx, change in enumerate(changes)
        ]
        async with async_session_scope() as db:
            service = self._message_service_factory(db)
            return await create_tool_result_message(
                session_id=session_id,
                content=blocks,
                task_id=task_id,
                index=0,
                message_service=service,
                source="codex-sdk",
            )

    async def _close_thinking(
        self,
        item_id: str,
        thinking_message_ids: dict[str, str],
        open_thinking_ids: set[str],
        streaming_callbacks: StreamingCallbacks | None,
    ) -> None:
        message_id = thinking_message_ids.get(item_id)
        if streaming_callbacks and message_id in open_thinking_ids:
            open_thinking_ids.remove(message_id)
            await streaming_callbacks.on_thinking_end(message_id)

    async def _close_all_thinking(
        self,
        thinking_message_ids: dict[str, str],
        open_thinking_ids: set[str],
        streaming_callbacks: StreamingCallbacks | None,
    ) -> None:
        if not streaming_callbacks:
            return
        for message_id in list(open_thinking_ids):
            await streaming_callbacks.on_thinking_end(message_id)
            open_thinking_ids.remove(message_id)

    @staticmethod
    def _context_window(token_usage: dict[str, Any] | None) -> int | None:
        if not token_usage:
            return None
        return codex_context_usage({"token_usage": token_usage})

    @staticmethod
    def _context_window_limit(token_usage: dict[str, Any] | None) -> int | None:
        if not token_usage:
            return None
        return token_usage.get("model_context_window")

    @staticmethod
    def _noop_emit_event(event_name: str, data: dict[str, Any]) -> None:
        logger.debug("Dropping Codex event without streaming callback: %s", event_name)
