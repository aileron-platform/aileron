"""ACP Tool implementation."""

from __future__ import annotations

import json
import logging
import shutil
import time
from typing import Any, Dict, Optional

from acp.helpers import text_block
from acp.schema import PromptResponse

from app.database import async_session_scope
from app.utils.datetime_utils import utcnow
from app.modules.agent_session.domain.enums import PermissionMode
from app.modules.agent_session.repositories.agent_session_repository import AgentSessionRepository
from app.modules.agent_session.repositories.message_repository import MessageRepository
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.tools.base.streaming_callbacks import StreamingCallbacks
from app.modules.agent_session.services.tools.base.tool_interface import ITool
from app.modules.agent_session.services.tools.base.types import TaskResult, ToolCapabilities, ToolType
from app.modules.file_system.workspace_service import WorkspaceDataService

from .connection_manager import AcpConnectionManager
from .message_builder import create_assistant_message, create_user_message

logger = logging.getLogger(__name__)

DEFAULT_COMMANDS = {
    ToolType.CODEX.value: "codex",
    ToolType.GEMINI.value: "gemini",
    ToolType.OPENCODE.value: "opencode",
}

DEFAULT_ARGS = {
    ToolType.CODEX.value: [],
    ToolType.GEMINI.value: ["--experimental-acp"],
    ToolType.OPENCODE.value: [],
}


class AcpTool(ITool):
    """ACP tool for codex/gemini/opencode.

    Stateless: does not hold DB session, each DB operation uses short-lived session
    (via async_session_scope), avoiding connection pool occupation during long-running tasks.
    """

    def __init__(
        self,
        tool_type: ToolType,
        workspace_service: Optional[WorkspaceDataService] = None,
        connection_manager: Optional[AcpConnectionManager] = None,
    ) -> None:
        self._tool_type = tool_type
        self.workspace_service = workspace_service or WorkspaceDataService()
        self.connection_manager = connection_manager or AcpConnectionManager()

    @property
    def tool_type(self) -> ToolType:
        return self._tool_type

    @property
    def name(self) -> str:
        return self._tool_type.value

    def get_capabilities(self) -> ToolCapabilities:
        return ToolCapabilities(
            streaming=True,
            thinking=True,
            multimodal=False,
            max_context_window=200000,
            prompt_caching=False,
            local_execution=True,
            built_in_tools=["file_operations", "terminal", "permission"],
            supports_session_import=False,
            supports_session_create=True,
            supports_live_execution=True,
        )

    async def check_installed(self) -> bool:
        command = DEFAULT_COMMANDS.get(self._tool_type.value, self._tool_type.value)
        return shutil.which(command) is not None

    async def execute_task(
        self,
        session_id: str,
        prompt: str,
        task_id: Optional[str] = None,
        permission_mode: Optional[PermissionMode] = None,
        streaming_callbacks: Optional[StreamingCallbacks] = None,
    ) -> TaskResult:
        logger.info(
            "ACP execute_task started: session_id=%s task_id=%s tool=%s prompt_len=%d",
            session_id,
            task_id,
            self._tool_type.value,
            len(prompt or ""),
        )
        # Get next message index and create user message (short-lived session)
        async with async_session_scope() as db:
            message_repo = MessageRepository(db)
            message_service = MessageService(db)
            existing_messages = await message_repo.find_by_session(session_id)
            next_index = len(existing_messages)

            user_message = await create_user_message(
                session_id=session_id,
                prompt=prompt,
                task_id=task_id,
                index=next_index,
                message_service=message_service,
            )
            # Session auto-commits when context ends

        if streaming_callbacks:
            await streaming_callbacks.on_message_created(user_message)

        next_index += 1

        # Get session and workspace settings (short-lived session)
        async with async_session_scope() as db:
            session_repo = AgentSessionRepository(db)
            session_model = await session_repo.find_by_id(session_id)
            if not session_model:
                raise ValueError(f"Session not found: {session_id}")
            session = session_repo.to_entity(session_model)

        workspace_info = await self.workspace_service.get_workspace(session.workspace_id)
        if not workspace_info:
            raise ValueError(f"Workspace not found: {session.workspace_id}")

        command = DEFAULT_COMMANDS.get(self._tool_type.value, self._tool_type.value)
        args = list(DEFAULT_ARGS.get(self._tool_type.value, []))
        if workspace_info.acp_cli_args:
            args.extend(workspace_info.acp_cli_args)
        env_vars = {item.key: item.value for item in workspace_info.env_vars}
        cwd = session.custom_context.get("workspace_path") or workspace_info.workspace_path

        connection = await self.connection_manager.get_or_create(
            session_id=session_id,
            tool_type=self._tool_type.value,
            command=command,
            args=args,
            env=env_vars or None,
            cwd=cwd,
            supports_terminal=True,
        )

        emit_event = None
        if streaming_callbacks and hasattr(streaming_callbacks, "emit_event"):
            emit_event = streaming_callbacks.emit_event
        connection.client_impl.set_task_context(
            task_id=task_id or "",
            streaming_callbacks=streaming_callbacks,
            emit_event=emit_event,
        )

        # Ensure ACP session exists
        sdk_session_id = await self._ensure_sdk_session(connection, session_id, session.sdk_session_id, cwd)

        stream_start = time.time()
        response: Optional[PromptResponse] = None
        try:
            response = await connection.connection.prompt(
                session_id=sdk_session_id,
                prompt=[text_block(prompt)],
            )
        finally:
            await connection.client_impl.finalize_streaming()

        content_text, thinking_text = connection.client_impl.get_current_content()
        tool_executions = connection.client_impl.get_tool_executions()

        content_blocks: list[dict[str, Any]] = []

        # Build tool_use / tool_result blocks from accumulated tool executions
        for idx, tex in enumerate(tool_executions):
            tool_use_id = tex.get("tool_call_id") or f"acp_tool_{idx}"
            tool_name = tex.get("title") or "tool"
            tool_input = tex.get("tool_input")
            if not isinstance(tool_input, dict):
                tool_input = {}
            else:
                tool_input = dict(tool_input)
            tool_input.setdefault("toolCallId", tool_use_id)

            content_blocks.append({
                "type": "tool_use",
                "id": tool_use_id,
                "name": tool_name,
                "input": tool_input,
            })

            # Build tool_result
            is_error = tex.get("is_error", False)
            result_content: Any = tex.get("tool_result")
            if result_content is None:
                fallback: dict[str, Any] = {"toolCallId": tool_use_id}
                status = tex.get("status")
                if status:
                    fallback["status"] = status
                content = tex.get("content")
                if content:
                    fallback["content"] = content
                result_content = fallback if len(fallback) > 1 else ""

            content_blocks.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result_content,
                "is_error": is_error,
            })

        if thinking_text:
            content_blocks.append({"type": "thinking", "thinking": thinking_text})
        if content_text:
            content_blocks.append({"type": "text", "text": content_text})
        if not content_blocks:
            content_blocks.append({"type": "text", "text": ""})

        # Create assistant message (short-lived session)
        async with async_session_scope() as db:
            message_service = MessageService(db)
            assistant_message = await create_assistant_message(
                session_id=session_id,
                content=content_blocks,
                task_id=task_id,
                index=next_index,
                message_service=message_service,
                metadata={
                    "model": None,
                    "stop_reason": response.stop_reason if response else None,
                },
            )
        assistant_message_id = assistant_message["message_id"]

        if streaming_callbacks:
            await streaming_callbacks.on_message_created(assistant_message)

        logger.info(
            "ACP execute_task completed: session_id=%s task_id=%s assistant_message_id=%s content_blocks=%d",
            session_id,
            task_id,
            assistant_message_id,
            len(content_blocks),
        )

        duration_ms = int((time.time() - stream_start) * 1000)
        raw_sdk_response: Optional[Dict[str, Any]] = None
        was_stopped = False
        if response:
            raw_sdk_response = response.model_dump(by_alias=True, exclude_none=True)
            was_stopped = response.stop_reason == "cancelled"

        return TaskResult(
            user_message_id=user_message["message_id"],
            assistant_message_ids=[assistant_message_id],
            duration_ms=duration_ms,
            agent_session_id=sdk_session_id,
            raw_sdk_response=raw_sdk_response,
            was_stopped=was_stopped,
        )

    async def stop_task(self, session_id: str, task_id: Optional[str] = None) -> dict:
        connection = self.connection_manager.get_existing(session_id)
        if connection and connection.sdk_session_id:
            await connection.connection.cancel(session_id=connection.sdk_session_id)
        return {"success": True}

    async def _ensure_sdk_session(
        self,
        connection: Any,
        session_id: str,
        existing_sdk_session_id: Optional[str],
        cwd: str,
    ) -> str:
        if connection.sdk_session_id:
            return connection.sdk_session_id

        if existing_sdk_session_id:
            try:
                await connection.connection.load_session(
                    session_id=existing_sdk_session_id,
                    cwd=cwd,
                    mcp_servers=[],
                )
                connection.sdk_session_id = existing_sdk_session_id
                return existing_sdk_session_id
            except Exception:
                logger.warning("Failed to load ACP session, creating a new one", exc_info=True)

        response = await connection.connection.new_session(cwd=cwd, mcp_servers=[])
        connection.sdk_session_id = response.session_id
        await self._persist_sdk_session_id(session_id, response.session_id)
        return response.session_id

    async def _persist_sdk_session_id(self, session_id: str, sdk_session_id: str) -> None:
        async with async_session_scope() as db:
            session_repo = AgentSessionRepository(db)
            model = await session_repo.find_by_id(session_id)
            if not model:
                return
            data = {}
            if model.data:
                try:
                    data = json.loads(model.data)
                except (TypeError, json.JSONDecodeError):
                    data = {}
            data["sdk_session_id"] = sdk_session_id
            update_payload = {
                "data": json.dumps(data, ensure_ascii=False),
                "updated_at": utcnow(),
            }
            await session_repo.update(session_id, update_payload)
