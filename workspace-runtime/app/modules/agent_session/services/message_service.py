"""Message Service.

Provides business logic for messages, including creation, query, queue management, etc.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.datetime_utils import utcnow

from ..domain.entities import Message
from ..domain.enums import MessageRole, MessageStatus, MessageType
from ..domain.value_objects import PermissionRequestContent, ToolUse
from ..repositories.message_repository import MessageRepository
from ..repositories.agent_session_repository import AgentSessionRepository
from ..schemas.message import MessageCreate, MessageQuery
from ..websocket.events import EventEmitter, get_event_emitter


class MessageServiceError(Exception):
    """Message Service error."""

    pass


class MessageService:
    """Message Service.

    Handles message-related business logic.
    """

    def __init__(
        self,
        db: AsyncSession,
        message_repo: Optional[MessageRepository] = None,
        session_repo: Optional[AgentSessionRepository] = None,
        emitter: Optional[EventEmitter] = None,
    ):
        """Initialize Service.

        Args:
            db: Database session
            message_repo: Message Repository (injectable)
            session_repo: Session Repository (injectable)
            emitter: WebSocket event emitter (injectable)
        """
        self.db = db
        self.message_repo = message_repo or MessageRepository(db)
        self.session_repo = session_repo or AgentSessionRepository(db)
        self.emitter = emitter or get_event_emitter()

    async def create_message(
        self,
        data: MessageCreate,
    ) -> Message:
        """Create message.

        Args:
            data: Creation request data

        Returns:
            Created message entity
        """
        message_id = str(uuid.uuid4())
        now = utcnow()

        # Get next index
        next_index = await self.message_repo.get_next_index(data.session_id)

        # Create data blob
        data_blob: Dict[str, Any] = {
            "content": data.content,
        }

        if data.tool_uses:
            data_blob["tool_uses"] = [
                {"id": tu.id, "name": tu.name, "input": tu.input}
                for tu in data.tool_uses
            ]

        if data.metadata:
            data_blob["metadata"] = data.metadata

        # Calculate content preview
        content_preview = self._get_content_preview(data.content)

        # Create record (data serialized to JSON string stored in TEXT field)
        model = await self.message_repo.create({
            "message_id": message_id,
            "created_at": now,
            "session_id": data.session_id,
            "task_id": data.task_id,
            "type": data.type.value,
            "role": data.role.value,
            "index": next_index,
            "timestamp": now,
            "content_preview": content_preview,
            "parent_tool_use_id": data.parent_tool_use_id,
            "data": self._json_dumps(data_blob),
        })

        # Update session's message_count
        await self.session_repo.increment_message_count(data.session_id)

        # If first user message, auto-set session title
        if data.role == MessageRole.USER and next_index == 0:
            await self._update_session_title_from_first_message(
                data.session_id, content_preview
            )

        return self.message_repo.to_entity(model)

    async def get_message(
        self,
        message_id: str,
    ) -> Optional[Message]:
        """Get message.

        Args:
            message_id: Message ID

        Returns:
            Message entity or None
        """
        model = await self.message_repo.find_by_id(message_id)
        if not model:
            return None

        return self.message_repo.to_entity(model)

    async def find_messages(
        self,
        query: MessageQuery,
    ) -> Tuple[List[Message], int]:
        """Query message list.

        Args:
            query: Query parameters

        Returns:
            (Message list, total)
        """
        if not query.session_id:
            raise MessageServiceError("session_id is required")

        # Query
        models = await self.message_repo.find_by_session(
            session_id=query.session_id,
            task_id=query.task_id,
            message_type=query.type,
            limit=query.limit,
            offset=query.offset,
        )

        # Calculate total
        filters = {"session_id": query.session_id, "status": None}
        if query.task_id:
            filters["task_id"] = query.task_id
        if query.type:
            filters["type"] = query.type.value

        total = await self.message_repo.count(filters)

        # Convert to entities
        messages = [self.message_repo.to_entity(m) for m in models]

        return messages, total

    async def find_by_task(
        self,
        task_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """Query messages by task ID.

        Args:
            task_id: Task ID
            limit: Max count
            offset: Offset

        Returns:
            Message list
        """
        models = await self.message_repo.find_by_task(task_id, limit, offset)
        return [self.message_repo.to_entity(m) for m in models]

    async def find_by_range(
        self,
        session_id: str,
        start_index: int,
        end_index: int,
    ) -> List[Message]:
        """Query messages by index range.

        Args:
            session_id: Session ID
            start_index: Start index
            end_index: End index

        Returns:
            Message list
        """
        models = await self.message_repo.find_by_range(
            session_id,
            start_index,
            end_index,
        )
        return [self.message_repo.to_entity(m) for m in models]

    async def create_bulk(
        self,
        messages: List[MessageCreate],
    ) -> List[Message]:
        """Batch create messages.

        Args:
            messages: Message creation request list

        Returns:
            Created message list
        """
        if not messages:
            return []

        session_id = messages[0].session_id
        now = utcnow()

        # Get starting index
        start_index = await self.message_repo.get_next_index(session_id)

        # Prepare batch data
        bulk_data = []
        for i, data in enumerate(messages):
            message_id = str(uuid.uuid4())

            data_blob: Dict[str, Any] = {
                "content": data.content,
            }

            if data.tool_uses:
                data_blob["tool_uses"] = [
                    {"id": tu.id, "name": tu.name, "input": tu.input}
                    for tu in data.tool_uses
                ]

            if data.metadata:
                data_blob["metadata"] = data.metadata

            content_preview = self._get_content_preview(data.content)

            bulk_data.append({
                "message_id": message_id,
                "created_at": now,
                "session_id": data.session_id,
                "task_id": data.task_id,
                "type": data.type.value,
                "role": data.role.value,
                "index": start_index + i,
                "timestamp": now,
                "content_preview": content_preview,
                "parent_tool_use_id": data.parent_tool_use_id,
                "data": self._json_dumps(data_blob),
            })

        # Batch create
        models = await self.message_repo.create_bulk(bulk_data)

        # Update session's message_count
        await self.session_repo.increment_message_count(session_id, len(messages))

        return [self.message_repo.to_entity(m) for m in models]

    async def delete_message(
        self,
        message_id: str,
    ) -> bool:
        """Delete message.

        Args:
            message_id: Message ID

        Returns:
            Whether deletion was successful
        """
        return await self.message_repo.delete(message_id)

    # === Queue management methods (moved to Queue Management Methods block)===
    # Old implementation removed, use new create_queued_message, get_queued_messages, etc.

    # === Permission request related ===

    async def create_permission_request(
        self,
        session_id: str,
        task_id: str,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
        decision_type: str = "permission",
        options: Optional[List[Dict[str, Any]]] = None,
        raw_tool_call: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
    ) -> Message:
        """Create permission request message.

        Args:
            session_id: Session ID
            task_id: Task ID
            request_id: Request ID
            tool_name: Tool name
            tool_input: Tool input
            tool_use_id: Tool Use ID

        Returns:
            Created permission request message
        """
        message_id = str(uuid.uuid4())
        now = utcnow()

        # Get next index
        next_index = await self.message_repo.get_next_index(session_id)

        # Create permission request content
        permission_content = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "decision_type": decision_type,
            "status": "pending",
        }
        if tool_use_id:
            permission_content["tool_use_id"] = tool_use_id
        if tool_call_id:
            permission_content["tool_call_id"] = tool_call_id
        if options is not None:
            permission_content["options"] = options
        if raw_tool_call is not None:
            permission_content["raw_tool_call"] = raw_tool_call

        data_blob: Dict[str, Any] = {
            "content": permission_content,
        }

        content_preview = f"Permission request: {tool_name}"

        model = await self.message_repo.create({
            "message_id": message_id,
            "created_at": now,
            "session_id": session_id,
            "task_id": task_id,
            "type": MessageType.PERMISSION_REQUEST.value,
            "role": MessageRole.SYSTEM.value,
            "index": next_index,
            "timestamp": now,
            "content_preview": content_preview,
            "data": self._json_dumps(data_blob),
        })

        # Update session's message_count
        await self.session_repo.increment_message_count(session_id)

        return self.message_repo.to_entity(model)

    async def update_permission_request(
        self,
        session_id: str,
        request_id: str,
        status: str,
        scope: Optional[str] = None,
        approved_by: Optional[str] = None,
        decision_type: Optional[str] = None,
        outcome: Optional[str] = None,
        option_id: Optional[str] = None,
        reason: Optional[str] = None,
        decision_content: Optional[str] = None,
    ) -> Optional[Message]:
        """Update permission request status.

        Args:
            session_id: Session ID
            request_id: Request ID
            status: New status
            scope: Permission scope
            approved_by: Approver

        Returns:
            Updated message or None
        """
        model = await self.message_repo.find_permission_request(session_id, request_id)
        if not model:
            return None

        # Deserialize data (JSON string -> dict)
        data = self._json_loads(model.data)
        content = data.get("content", {})

        content["status"] = status
        if decision_type:
            content["decision_type"] = decision_type
        if outcome:
            content["outcome"] = outcome
        if option_id:
            content["option_id"] = option_id
        if scope:
            content["scope"] = scope
        if approved_by:
            content["approved_by"] = approved_by
            content["approved_at"] = utcnow().isoformat()
        if reason:
            content["reason"] = reason
        if decision_content is not None:
            content["content"] = decision_content

        data["content"] = content

        # Serialize and update (dict -> JSON string)
        updated_model = await self.message_repo.update(model.message_id, {"data": self._json_dumps(data)})
        if not updated_model:
            return None

        return self.message_repo.to_entity(updated_model)

    # =====================================================
    # Queue Management Methods
    # =====================================================

    async def create_queued_message(
        self,
        session_id: str,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
        queued_by_user_id: Optional[str] = None,
    ) -> Message:
        """Create queued message.

        Args:
            session_id: Session ID
            prompt: Prompt content
            metadata: Additional metadata
            queued_by_user_id: User ID who created this message (for authentication)

        Returns:
            Created queued message entity
        """
        # Merge metadata, add authentication info
        combined_metadata = metadata or {}
        if queued_by_user_id:
            combined_metadata["queued_by_user_id"] = queued_by_user_id
        combined_metadata["queued_at"] = utcnow().isoformat()

        model = await self.message_repo.create_queued(
            session_id=session_id,
            prompt=prompt,
            metadata=combined_metadata if combined_metadata else None,
        )
        return self.message_repo.to_entity(model)

    async def count_queued_messages(self, session_id: str) -> int:
        """Count queued messages in session.

        Args:
            session_id: Session ID

        Returns:
            Queued messages count
        """
        return await self.message_repo.count_queued(session_id)

    async def get_queued_messages(self, session_id: str) -> List[Message]:
        """Get all queued messages.

        Args:
            session_id: Session ID

        Returns:
            Queued messages list
        """
        models = await self.message_repo.find_queued(session_id)
        return [self.message_repo.to_entity(m) for m in models]

    async def delete_queued_message(self, message_id: str) -> bool:
        """Delete queued message.

        Args:
            message_id: Message ID

        Returns:
            Whether deletion was successful
        """
        return await self.message_repo.delete_queued(message_id)

    async def claim_next_queued_message(self, session_id: str) -> Optional[Message]:
        """Claim next queued message and mark as dispatching."""
        model = await self.message_repo.claim_next_queued(session_id)
        if not model:
            return None
        return self.message_repo.to_entity(model)

    async def restore_dispatching_message(self, message_id: str) -> bool:
        """Restore dispatching message to queued."""
        return await self.message_repo.restore_dispatching(message_id)

    async def finalize_dispatching_message(self, message_id: str) -> bool:
        """Delete dispatching message that was successfully executed."""
        return await self.message_repo.delete_dispatching(message_id)

    # NOTE: Old alias methods add_to_queue, get_queue removed
    # Use create_queued_message, get_queued_messages directly

    def _json_dumps(self, data: Dict[str, Any]) -> str:
        """Serialize dict to JSON string (for storing in TEXT field).

        Automatically cleans NULL bytes (\\x00), as PostgreSQL TEXT field doesn't support them.

        Args:
            data: Dict to serialize

        Returns:
            JSON string (NULL bytes cleaned)
        """
        json_str = json.dumps(data, ensure_ascii=False)
        # Clean NULL bytes to avoid PostgreSQL errors
        return json_str.replace('\x00', '')

    def _json_loads(self, data: Optional[str]) -> Dict[str, Any]:
        """Deserialize JSON string to dict (read from TEXT field).

        Args:
            data: JSON string or None

        Returns:
            Dict, or empty dict if data is None or parsing fails
        """
        if not data:
            return {}
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON from database TEXT field",
                extra={
                    "error": str(e),
                    "data_length": len(data) if data else 0,
                    "data_preview": data[:100] if data else None,
                }
            )
            return {}

    def _get_content_preview(
        self,
        content: Union[str, List[Dict[str, Any]], Dict[str, Any]],
        max_length: int = 200,
    ) -> str:
        """Get content preview.

        Args:
            content: Message content
            max_length: Maximum length

        Returns:
            Content preview string
        """
        if isinstance(content, str):
            return content[:max_length]

        if isinstance(content, list):
            # Find first text block
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    return text[:max_length]

        if isinstance(content, dict):
            # May be PermissionRequestContent
            if "request_id" in content:
                return f"Permission request: {content.get('tool_name', '')}"
            if "text" in content:
                return content["text"][:max_length]

        return ""

    async def _update_session_title_from_first_message(
        self,
        session_id: str,
        content_preview: str,
        max_length: int = 50,
    ) -> None:
        """Update session title from first message.

        Args:
            session_id: Session ID
            content_preview: Message content preview
            max_length: title Maximum length
        """
        # Check if session already has a title
        session_model = await self.session_repo.find_by_id(session_id)
        if not session_model:
            return

        session = self.session_repo.to_entity(session_model)
        if session.title:
            # Title already exists, not overwriting
            return

        # Truncate and clean title
        title = content_preview.strip()
        if len(title) > max_length:
            title = title[:max_length - 3] + "..."

        # Remove newline characters
        title = title.replace("\n", " ").replace("\r", "")

        # Update session title
        if title:
            # Deserialize data (JSON string -> dict)
            try:
                data = json.loads(session_model.data) if session_model.data else {}
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    "Failed to deserialize session data when updating title",
                    extra={
                        "error": str(e),
                        "session_id": session_id,
                    }
                )
                data = {}
            data["title"] = title
            # Serialize and update (dict -> JSON string, clean NULL bytes)
            json_str = json.dumps(data, ensure_ascii=False).replace('\x00', '')
            await self.session_repo.update(session_id, {"data": json_str})

            # Emit WebSocket event to notify frontend to update session list
            await self.emitter.emit_session_patched(
                session_id,
                {
                    "session_id": session_id,
                    "title": title,
                    "workspace_id": session.workspace_id,
                }
            )


__all__ = [
    "MessageService",
    "MessageServiceError",
]
