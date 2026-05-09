"""Agent Session Service.

Provides business logic for sessions, including creation, query, and prompt execution.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.modules.version_control.utils import GitUtils
from app.modules.version_control.worktree_config import get_worktree_subdir
from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

ALLOWED_WORKSPACE_PATH_ROOTS = (Path("/workspace"), Path("/knowledge"))

from ..domain.entities import AgentSession
from ..domain.enums import AgenticTool, AgentSessionStatus, GeminiPermissionMode, PermissionMode
from ..domain.value_objects import (
    ModelConfig,
    PermissionConfig,
    TOOL_CAPABILITIES,
    ToolCapabilities,
    get_tool_capabilities,
)
from ..repositories.agent_session_repository import AgentSessionRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionQuery,
    AgentSessionResponse,
    AgentSessionUpdate,
)
from ..websocket.events import EventEmitter, get_event_emitter


class AgentSessionValidationError(Exception):
    """Agent session validation error with localizable metadata."""

    def __init__(self, *, error_code: str, message_key: str, params: dict[str, Any] | None = None) -> None:
        super().__init__(message_key)
        self.error_code = error_code
        self.message_key = message_key
        self.params = params or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize validation error for API responses."""
        return {
            "errorCode": self.error_code,
            "messageKey": self.message_key,
            "params": self.params,
        }


class AgentSessionService:
    """Agent Session Service.

    Handles session-related business logic.
    """

    def __init__(
        self,
        db: AsyncSession,
        session_repo: Optional[AgentSessionRepository] = None,
        task_repo: Optional[TaskRepository] = None,
        emitter: Optional[EventEmitter] = None,
        git_utils: Optional[GitUtils] = None,
    ):
        """Initialize Service.

        Args:
            db: Database session
            session_repo: Session Repository (injectable)
            task_repo: Task Repository (injectable)
            emitter: Event Emitter (injectable)
        """
        self.db = db
        self.session_repo = session_repo or AgentSessionRepository(db)
        self.task_repo = task_repo or TaskRepository(db)
        self.emitter = emitter or get_event_emitter()
        workspace_root = Path(get_settings().WORKSPACE_PATH).resolve()
        self.git_utils = git_utils or GitUtils(workspace_root, worktree_subdir=get_worktree_subdir())

    async def create_session(
        self,
        data: AgentSessionCreate,
    ) -> AgentSession:
        """Create session.

        Args:
            data: Creation request data

        Returns:
            Created session entity
        """
        session_id = str(uuid.uuid4())
        now = utcnow()
        custom_context: Dict[str, Any] = {}

        if data.git_context_id:
            workspace_path = str(
                self.git_utils.resolve_context_path(
                    data.workspace_id,
                    data.git_context_id,
                )
            )
            custom_context["git_context_id"] = data.git_context_id
            custom_context["workspace_path"] = workspace_path

        if data.workspace_path:
            custom_context["workspace_path"] = self._validate_workspace_path(data.workspace_path)

        # Create data blob
        data_blob: Dict[str, Any] = {
            "tasks": [],
            "message_count": 0,
            "contextFiles": data.context_files,
        }
        if custom_context:
            data_blob["custom_context"] = custom_context

        if data.title:
            data_blob["title"] = data.title

        permission_config = self._build_permission_config_blob(
            agentic_tool=data.agentic_tool,
            permission_config=data.permission_config,
        )
        if permission_config:
            data_blob["permission_config"] = permission_config

        if data.model_settings:
            data_blob["model_config"] = {
                "mode": data.model_settings.mode,
                "model": data.model_settings.model,
                "updated_at": now.isoformat(),
            }
            if data.model_settings.thinking_mode:
                data_blob["model_config"]["thinkingMode"] = data.model_settings.thinking_mode
            if data.model_settings.manual_thinking_tokens:
                data_blob["model_config"]["manualThinkingTokens"] = data.model_settings.manual_thinking_tokens
            if data.model_settings.provider:
                data_blob["model_config"]["provider"] = data.model_settings.provider

        # Set context window limit
        tool_caps = get_tool_capabilities(data.agentic_tool.value)
        if tool_caps:
            data_blob["context_window_limit"] = tool_caps.max_context_window

        # Create record (data serialized to JSON string stored in TEXT field)
        model = await self.session_repo.create({
            "session_id": session_id,
            "created_at": now,
            "created_by": data.user_id or "anonymous",
            "status": AgentSessionStatus.IDLE.value,
            "agentic_tool": data.agentic_tool.value,
            "workspace_id": data.workspace_id,
            "source": data.source,
            "ready_for_prompt": True,
            "archived": False,
            "data": json.dumps(data_blob, ensure_ascii=False),
        })

        session_entity = self.session_repo.to_entity(model)

        # Send sessions:created event
        logger.debug("Sending sessions:created event - session_id=%s", session_id)
        try:
            sent_count = await self.emitter.emit_session_created(
                session_id=session_id,
                data=self._session_to_event_data(session_entity),
            )
            logger.debug("sessions:created event sent to %d connections", sent_count)
        except Exception as e:
            logger.error("Failed to send sessions:created event: %s", e)

        return session_entity

    def _build_permission_config_blob(
        self,
        *,
        agentic_tool: AgenticTool,
        permission_config: Any | None,
    ) -> Dict[str, Any] | None:
        """Build persisted permission config with Gemini defaults applied."""
        if permission_config is None:
            if agentic_tool != AgenticTool.GEMINI:
                return None
            return {
                "mode": PermissionMode.DEFAULT.value,
                "gemini": GeminiPermissionMode.YOLO.value,
            }

        config_data: Dict[str, Any] = {
            "mode": permission_config.mode.value,
        }
        if permission_config.codex:
            config_data["codex"] = permission_config.codex
        if agentic_tool == AgenticTool.GEMINI:
            config_data["gemini"] = permission_config.gemini or GeminiPermissionMode.YOLO.value
        elif permission_config.gemini:
            config_data["gemini"] = permission_config.gemini
        return config_data

    async def get_session(
        self,
        session_id: str,
    ) -> Optional[AgentSession]:
        """Get session.

        Args:
            session_id: Session ID

        Returns:
            Session entity or None
        """
        model = await self.session_repo.find_by_id(session_id)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def find_sessions(
        self,
        query: AgentSessionQuery,
    ) -> Tuple[List[AgentSession], int]:
        """Query session list.

        Args:
            query: Query parameters

        Returns:
            (Session list, total)
        """
        # Build filter conditions
        filters: Dict[str, Any] = {"archived": query.archived}

        if query.workspace_id:
            filters["workspace_id"] = query.workspace_id
        if query.status:
            filters["status"] = query.status.value
        if query.agentic_tool:
            filters["agentic_tool"] = query.agentic_tool.value
        if query.source:
            filters["source"] = query.source

        # Query
        models = await self.session_repo.find_all(
            filters=filters,
            limit=query.limit,
            offset=query.offset,
            order_by="created_at",
            order_desc=True,
        )

        # Count total
        total = await self.session_repo.count(filters)

        # Convert to entities
        sessions = [self.session_repo.to_entity(m) for m in models]

        return sessions, total

    async def update_session(
        self,
        session_id: str,
        data: AgentSessionUpdate,
    ) -> Optional[AgentSession]:
        """Update session.

        Args:
            session_id: Session ID
            data: Update data

        Returns:
            Updated session or None
        """
        existing = await self.session_repo.find_by_id(session_id)
        if not existing:
            return None

        update_data: Dict[str, Any] = {}

        if data.status is not None:
            update_data["status"] = data.status.value

        if data.archived is not None:
            update_data["archived"] = data.archived

        if data.archived_reason is not None:
            update_data["archived_reason"] = data.archived_reason

        # Update data blob
        if data.title is not None or data.permission_config is not None or data.model_settings is not None:
            # Deserialize existing data (JSON string -> dict)
            existing_data = json.loads(existing.data) if existing.data else {}

            if data.title is not None:
                existing_data["title"] = data.title

            if data.permission_config is not None:
                existing_data["permission_config"] = self._build_permission_config_blob(
                    agentic_tool=AgenticTool(existing.agentic_tool),
                    permission_config=data.permission_config,
                )

            if data.model_settings is not None:
                existing_data["model_config"] = {
                    "mode": data.model_settings.mode,
                    "model": data.model_settings.model,
                    "updated_at": utcnow().isoformat(),
                }
                if data.model_settings.thinking_mode:
                    existing_data["model_config"]["thinkingMode"] = data.model_settings.thinking_mode
                if data.model_settings.manual_thinking_tokens:
                    existing_data["model_config"]["manualThinkingTokens"] = data.model_settings.manual_thinking_tokens
                if data.model_settings.provider:
                    existing_data["model_config"]["provider"] = data.model_settings.provider

            # Serialize and update (dict -> JSON string)
            update_data["data"] = json.dumps(existing_data, ensure_ascii=False)

        if not update_data:
            return self.session_repo.to_entity(existing)

        model = await self.session_repo.update(session_id, update_data)
        if not model:
            return None

        session_entity = self.session_repo.to_entity(model)

        # Send sessions:patched event
        await self.emitter.emit_session_patched(
            session_id=session_id,
            data=self._session_to_event_data(session_entity),
        )

        return session_entity

    async def delete_session(
        self,
        session_id: str,
    ) -> bool:
        """Delete session.

        Args:
            session_id: Session ID

        Returns:
            Whether deletion succeeded
        """
        # Clean up related resources
        from .execution_service import ExecutionService
        ExecutionService.cleanup_session_lock(session_id)

        return await self.session_repo.delete(session_id)

    async def archive_session(
        self,
        session_id: str,
        reason: str = "manual",
    ) -> Optional[AgentSession]:
        """Archive session.

        Args:
            session_id: Session ID
            reason: Archive reason

        Returns:
            Updated session or None
        """
        model = await self.session_repo.archive(session_id, reason)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def get_current_execution(
        self,
        workspace_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get currently executing session in workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            Execution state info or None
        """
        model = await self.session_repo.find_running_by_workspace(workspace_id)
        if not model:
            return {
                "has_active_execution": False,
            }

        # Query active task
        active_task = await self.task_repo.find_active_by_session(model.session_id)

        return {
            "has_active_execution": True,
            "session_id": model.session_id,
            "task_id": active_task.id if active_task else None,
            "agentic_tool": model.agentic_tool,
            "started_at": active_task.started_at if active_task else None,
        }

    async def update_status(
        self,
        session_id: str,
        status: AgentSessionStatus,
    ) -> Optional[AgentSession]:
        """Update session status.

        Args:
            session_id: Session ID
            status: New status

        Returns:
            Updated session or None
        """
        model = await self.session_repo.update_status(session_id, status)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def add_task(
        self,
        session_id: str,
        task_id: str,
    ) -> Optional[AgentSession]:
        """Add task to session.

        Args:
            session_id: Session ID
            task_id: Task ID

        Returns:
            Updated session or None
        """
        model = await self.session_repo.add_task(session_id, task_id)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def increment_message_count(
        self,
        session_id: str,
        count: int = 1,
    ) -> Optional[AgentSession]:
        """Increment message count.

        Args:
            session_id: Session ID
            count: Increment amount

        Returns:
            Updated session or None
        """
        model = await self.session_repo.increment_message_count(session_id, count)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def update_context_usage(
        self,
        session_id: str,
        usage: int,
        limit: Optional[int] = None,
    ) -> Optional[AgentSession]:
        """Update Context Window usage.

        Args:
            session_id: Session ID
            usage: Current usage
            limit: Context limit

        Returns:
            Updated session or None
        """
        model = await self.session_repo.update_context_usage(session_id, usage, limit)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    @staticmethod
    def get_tool_capabilities(tool: str) -> Optional[ToolCapabilities]:
        """Get tool capabilities.

        Args:
            tool: Tool name

        Returns:
            Tool capabilities description
        """
        return get_tool_capabilities(tool)

    @staticmethod
    def get_all_tool_capabilities() -> Dict[str, ToolCapabilities]:
        """Get all tool capabilities.

        Returns:
            All tool capabilities descriptions
        """
        return TOOL_CAPABILITIES

    @staticmethod
    def _validate_workspace_path(workspace_path: str) -> str:
        """Validate an explicit runtime workspace path."""
        raw_path = Path(workspace_path)
        if not raw_path.is_absolute():
            raise AgentSessionValidationError(
                error_code="AGENT_SESSION_WORKSPACE_PATH_NOT_ABSOLUTE",
                message_key="agentSession.errors.workspacePath.notAbsolute",
                params={"field": "workspacePath"},
            )
        candidate = raw_path.resolve(strict=False)

        for root in ALLOWED_WORKSPACE_PATH_ROOTS:
            if candidate == root or root in candidate.parents:
                return str(candidate)

        allowed_roots = [str(root) for root in ALLOWED_WORKSPACE_PATH_ROOTS]
        raise AgentSessionValidationError(
            error_code="AGENT_SESSION_WORKSPACE_PATH_OUTSIDE_ALLOWED_ROOTS",
            message_key="agentSession.errors.workspacePath.outsideAllowedRoots",
            params={"field": "workspacePath", "allowedRoots": allowed_roots},
        )

    @staticmethod
    def _session_to_event_data(session: AgentSession) -> Dict[str, Any]:
        """Convert AgentSession entity to event data.

        Contains complete session information for WebSocket event broadcast.

        Args:
            session: AgentSession entity

        Returns:
            Event data dictionary
        """
        data = {
            "session_id": session.id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "created_by": session.created_by,
            "status": session.status.value if hasattr(session.status, "value") else session.status,
            "agentic_tool": session.agentic_tool.value if hasattr(session.agentic_tool, "value") else session.agentic_tool,
            "workspace_id": session.workspace_id,
            "source": session.source,
            "ready_for_prompt": session.ready_for_prompt,
            "archived": session.archived,
        }

        # Add info from Session entity
        if session.title:
            data["title"] = session.title
        if session.message_count > 0:
            data["message_count"] = session.message_count
        if session.tasks:
            data["tasks"] = session.tasks
        if session.permission_config:
            data["permission_config"] = session.permission_config.to_dict()
        if session.model_settings:
            data["model_config"] = session.model_settings.to_dict()

        return data


__all__ = ["AgentSessionService", "AgentSessionValidationError"]
